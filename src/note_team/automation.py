from __future__ import annotations

import email.utils
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from note_team.orchestrator import WorkflowRunner, slugify


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]{2,}")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass
class TopicSpec:
    id: str
    label: str
    description: str
    output_dir: str
    publish: bool = True
    automation_enabled: bool = False
    target_reader: str = ""
    tone: str = ""
    feed_urls: list[str] = field(default_factory=list)
    preferred_domains: list[str] = field(default_factory=list)
    style_guide: dict[str, Any] = field(default_factory=dict)
    brief_template: dict[str, Any] = field(default_factory=dict)
    quality_gates: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedEntry:
    title: str
    link: str
    summary: str
    published_at: datetime | None
    source_domain: str


@dataclass
class PublishedArticle:
    path: Path
    title: str
    summary: str
    tokens: set[str]


def load_topic_catalog(path: Path) -> list[TopicSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    topics: list[TopicSpec] = []
    for item in raw.get("topics", []):
        topics.append(
            TopicSpec(
                id=str(item["id"]),
                label=str(item["label"]),
                description=str(item.get("description") or ""),
                output_dir=str(item["output_dir"]),
                publish=bool(item.get("publish", True)),
                automation_enabled=bool(item.get("automation_enabled", False)),
                target_reader=str(item.get("target_reader") or ""),
                tone=str(item.get("tone") or ""),
                feed_urls=[str(url) for url in item.get("feed_urls", [])],
                preferred_domains=[str(domain) for domain in item.get("preferred_domains", [])],
                style_guide=dict(item.get("style_guide") or {}),
                brief_template=dict(item.get("brief_template") or {}),
                quality_gates=dict(item.get("quality_gates") or {}),
            )
        )
    return topics


def _strip_html(text: str) -> str:
    cleaned = HTML_TAG_PATTERN.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def _read_title_and_summary(path: Path) -> tuple[str, str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    title = ""
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break
    if not title:
        title = path.stem
    body = " ".join(line for line in lines if not line.startswith("#"))
    return title, body[:220]


def load_published_articles(content_root: Path) -> list[PublishedArticle]:
    articles: list[PublishedArticle] = []
    for path in sorted(content_root.rglob("*.md")):
        if path.name.lower().startswith("readme"):
            continue
        title, summary = _read_title_and_summary(path)
        articles.append(
            PublishedArticle(
                path=path,
                title=title,
                summary=summary,
                tokens=_tokenize(f"{title} {summary}"),
            )
        )
    return articles


def article_overlap_score(text: str, article: PublishedArticle) -> float:
    tokens = _tokenize(text)
    if not tokens or not article.tokens:
        return 0.0
    intersection = len(tokens & article.tokens)
    union = len(tokens | article.tokens)
    return intersection / union if union else 0.0


def candidate_overlap_score(entry: FeedEntry, article: PublishedArticle) -> float:
    combined_text = f"{entry.title} {entry.summary}".strip()
    body_overlap = article_overlap_score(combined_text, article)
    title_overlap = article_overlap_score(entry.title, article)
    return max(body_overlap, title_overlap)


def parse_feed(url: str, timeout_seconds: int = 20) -> list[FeedEntry]:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        data = response.read()
    root = ET.fromstring(data)
    entries: list[FeedEntry] = []

    channel = root.find("channel")
    if channel is not None:
        items = channel.findall("item")
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            summary = _strip_html(item.findtext("description") or "")
            published_text = (item.findtext("pubDate") or "").strip()
            published_at = None
            if published_text:
                try:
                    published_at = email.utils.parsedate_to_datetime(published_text)
                except (TypeError, ValueError):
                    published_at = None
            domain = urllib.parse.urlparse(link).netloc.lower()
            if title and link:
                entries.append(
                    FeedEntry(
                        title=title,
                        link=link,
                        summary=summary,
                        published_at=published_at,
                        source_domain=domain,
                    )
                )
        return entries

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.findall("atom:entry", namespace):
        title = (item.findtext("atom:title", default="", namespaces=namespace) or "").strip()
        summary = _strip_html(item.findtext("atom:summary", default="", namespaces=namespace) or "")
        link = ""
        for link_node in item.findall("atom:link", namespace):
            href = (link_node.attrib.get("href") or "").strip()
            if href:
                link = href
                break
        published_text = (
            item.findtext("atom:updated", default="", namespaces=namespace)
            or item.findtext("atom:published", default="", namespaces=namespace)
        ).strip()
        published_at = None
        if published_text:
            try:
                published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        domain = urllib.parse.urlparse(link).netloc.lower()
        if title and link:
            entries.append(
                FeedEntry(
                    title=title,
                    link=link,
                    summary=summary,
                    published_at=published_at,
                    source_domain=domain,
                )
            )
    return entries


def collect_recent_entries(topic: TopicSpec, max_age_hours: int) -> list[FeedEntry]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    entries: list[FeedEntry] = []
    for url in topic.feed_urls:
        try:
            feed_entries = parse_feed(url)
        except Exception:
            continue
        for entry in feed_entries:
            if entry.published_at and entry.published_at.tzinfo is None:
                entry.published_at = entry.published_at.replace(tzinfo=timezone.utc)
            if entry.published_at and entry.published_at < cutoff:
                continue
            entries.append(entry)
    deduped: dict[str, FeedEntry] = {}
    for entry in entries:
        key = f"{entry.title}|{entry.link}"
        deduped[key] = entry
    sorted_entries = sorted(
        deduped.values(),
        key=lambda item: item.published_at or datetime.now(timezone.utc),
        reverse=True,
    )
    return sorted_entries[:12]


def choose_article_candidate(
    topics: list[TopicSpec],
    published_articles: list[PublishedArticle],
    max_age_hours: int,
) -> tuple[TopicSpec, FeedEntry, list[PublishedArticle], PublishedArticle | None, str]:
    best_choice: tuple[float, TopicSpec, FeedEntry, list[PublishedArticle], PublishedArticle | None, str] | None = None
    for topic in topics:
        if not topic.automation_enabled:
            continue
        entries = collect_recent_entries(topic, max_age_hours=max_age_hours)
        for entry in entries:
            related = sorted(
                published_articles,
                key=lambda article: candidate_overlap_score(entry, article),
                reverse=True,
            )[:5]
            highest_overlap = candidate_overlap_score(entry, related[0]) if related else 0.0
            if highest_overlap >= 0.58:
                continue
            article_mode = "update" if highest_overlap >= 0.36 and related else "new"
            target_article = related[0] if article_mode == "update" and related else None
            freshness_bonus = 1.0
            if entry.published_at:
                freshness_bonus = max(0.1, 1 - (datetime.now(timezone.utc) - entry.published_at).total_seconds() / 86400)
            authority_bonus = 0.3 if any(domain in entry.source_domain for domain in topic.preferred_domains) else 0.0
            update_penalty = 0.08 if article_mode == "update" else 0.0
            score = freshness_bonus + authority_bonus - (highest_overlap * 1.35) - update_penalty
            if best_choice is None or score > best_choice[0]:
                best_choice = (score, topic, entry, related, target_article, article_mode)
    if best_choice is None:
        raise RuntimeError("fresh feed entry not found; no automation topic could produce a non-duplicate article")
    return best_choice[1], best_choice[2], best_choice[3], best_choice[4], best_choice[5]


def load_research_cache(project_root: Path, topic: TopicSpec) -> dict[str, Any]:
    cache_dir = project_root / "automation" / "cache"
    cache_path = cache_dir / f"{topic.id}.json"
    if not cache_path.exists():
        return {"topic_id": topic.id, "entries": []}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"topic_id": topic.id, "entries": []}


def update_research_cache(project_root: Path, topic: TopicSpec, entry: FeedEntry, published_path: Path | None) -> None:
    cache_dir = project_root / "automation" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{topic.id}.json"
    current = load_research_cache(project_root, topic)
    entries = list(current.get("entries") or [])
    entries.insert(
        0,
        {
            "title": entry.title,
            "link": entry.link,
            "summary": entry.summary[:240],
            "published_path": str(published_path) if published_path else "",
            "cached_at": datetime.now().isoformat(),
        },
    )
    current["entries"] = entries[:20]
    cache_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_brief_payload(
    topic: TopicSpec,
    entry: FeedEntry,
    related_articles: list[PublishedArticle],
    research_cache: dict[str, Any],
    article_mode: str,
    target_article: PublishedArticle | None,
) -> dict[str, Any]:
    related_lines = [
        f"{article.title}: {article.summary[:120]}"
        for article in related_articles
        if article.summary
    ]
    objective = topic.brief_template.get(
        "objective",
        f"{topic.label}に関する国・民間・世間の最新動向を整理し、読者が次の判断をしやすい記事にする",
    )
    topic_line = f"{topic.label}の{'更新' if article_mode == 'update' else '最新動向'}を整理する: {entry.title}"
    cached_lines = [
        f"キャッシュ済み論点: {item.get('title', '')}: {str(item.get('summary', ''))[:100]}"
        for item in list(research_cache.get("entries") or [])[:5]
        if item.get("title")
    ]
    sections = topic.brief_template.get("sections_to_cover") or [
        "今何が起きたか",
        "国・民間・生活者のどこに影響するか",
        "過去の流れとの違い",
        "読者が次に見るべき論点",
    ]
    delta_instruction = (
        f"更新対象記事: {target_article.path} / {target_article.title}"
        if target_article else "新規記事として扱う"
    )
    return {
        "topic": topic_line,
        "objective": objective,
        "target_reader": topic.target_reader or "最新動向を短時間で把握したい実務担当者",
        "angle": topic.brief_template.get("angle") or f"ニュース要約ではなく、{topic.label}の構造変化と実務インパクトを読む",
        "tone": topic.tone or "事実ベースで簡潔",
        "call_to_action": topic.style_guide.get("cta_style") or "自組織で見るべき論点を1つだけ決めて次の確認行動に移してください。",
        "constraints": [
            "最新時点の情報を優先し、古い認識を断定しない",
            "既存掲載済み記事と同じ切り口を繰り返さない",
            "一次情報や公式発表を優先し、不確実性は明示する",
            "見出しだけのニュース要約ではなく、流れと意味を整理する",
            delta_instruction,
        ],
        "keywords": [topic.label, "最新動向", "実務", "生成AI", "DX"],
        "reference_notes": [
            f"注目トリガー: {entry.title}",
            f"参照リンク: {entry.link}",
            f"要約: {entry.summary or '要約なし'}",
            *cached_lines,
            *([f"重複回避対象: {line}" for line in related_lines] or ["重複回避対象: 既存記事全体を広く参照する"]),
        ],
        "sections_to_cover": sections,
        "supporting_data": [
            entry.link,
            *[str(article.path) for article in related_articles[:3]],
        ],
        "extra": {
            "automation_topic_id": topic.id,
            "automation_source_url": entry.link,
            "automation_source_title": entry.title,
            "published_context": related_lines,
            "article_mode": article_mode,
            "target_article_path": str(target_article.path) if target_article else "",
            "style_guide": topic.style_guide,
            "quality_gates": topic.quality_gates,
            "preferred_domains": topic.preferred_domains,
        },
    }


def write_brief_file(project_root: Path, brief_payload: dict[str, Any]) -> Path:
    automation_dir = project_root / "automation" / "briefs"
    automation_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    brief_path = automation_dir / f"{timestamp}-{slugify(brief_payload['topic'])}.json"
    brief_path.write_text(json.dumps(brief_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return brief_path


def copy_final_article(
    run_dir: Path,
    content_root: Path,
    topic: TopicSpec,
    article_slug: str,
    article_mode: str,
    target_article: PublishedArticle | None,
) -> Path:
    final_article = run_dir / "FINAL_ARTICLE.md"
    target_dir = content_root / topic.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    if article_mode == "update" and target_article:
        target_path = target_article.path
    else:
        target_path = target_dir / f"{datetime.now():%Y-%m-%d}-{article_slug}.md"
    shutil.copy2(final_article, target_path)
    return target_path


def rebuild_publish_site(project_root: Path) -> None:
    subprocess.run(
        [sys.executable, "scripts/build_publish_site.py"],
        cwd=project_root,
        check=True,
    )


def run_automation_cycle(
    project_root: Path,
    team_config_path: Path,
    catalog_path: Path,
    content_root: Path,
    output_root: Path,
    mode: str,
    runner_command: str | None,
    max_age_hours: int = 8,
) -> dict[str, Any]:
    topics = load_topic_catalog(catalog_path)
    published_articles = load_published_articles(content_root)
    topic, entry, related_articles, target_article, article_mode = choose_article_candidate(
        topics=topics,
        published_articles=published_articles,
        max_age_hours=max_age_hours,
    )
    research_cache = load_research_cache(project_root, topic)
    brief_payload = build_brief_payload(topic, entry, related_articles, research_cache, article_mode, target_article)
    brief_path = write_brief_file(project_root, brief_payload)

    runner = WorkflowRunner(project_root=project_root, team_config_path=team_config_path)
    published_path: Path | None = None
    try:
        run_dir = runner.run(
            brief_path=brief_path,
            output_root=output_root,
            mode=mode,
            run_name=f"auto-{topic.id}-{slugify(entry.title)}",
            command=runner_command,
        )
        article_slug = slugify(entry.title)
        published_path = copy_final_article(run_dir, content_root, topic, article_slug, article_mode, target_article)
        rebuild_publish_site(project_root)
    except Exception as error:
        result = {
            "topic_id": topic.id,
            "topic_label": topic.label,
            "source_title": entry.title,
            "source_url": entry.link,
            "brief_path": str(brief_path),
            "run_dir": "",
            "published_path": "",
            "status": "brief_only",
            "error": str(error),
            "article_mode": article_mode,
        }
        state_dir = project_root / "automation" / "runs"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path = state_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{topic.id}.json"
        state_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        update_research_cache(project_root, topic, entry, None)
        return result

    result = {
        "topic_id": topic.id,
        "topic_label": topic.label,
        "source_title": entry.title,
        "source_url": entry.link,
        "brief_path": str(brief_path),
        "run_dir": str(run_dir),
        "published_path": str(published_path),
        "status": "published",
        "article_mode": article_mode,
    }
    state_dir = project_root / "automation" / "runs"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{topic.id}.json"
    state_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_research_cache(project_root, topic, entry, published_path)
    return result
