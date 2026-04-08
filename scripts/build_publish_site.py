#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import markdown

CATALOG_PATH = Path("config/topic_catalog.json")
REPO_URL = "https://github.com/zukkiii324/self-research"
SITE_TITLE = "Editorial Playground"
DATE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})")


@dataclass
class TopicGroup:
    source_group: str
    slug: str
    label: str
    description: str
    target_reader: str
    tone: str
    style_guide: dict[str, str]


@dataclass
class Article:
    anchor: str
    title: str
    summary: str
    rendered: str
    section_labels: list[str]
    highlight_points: list[str]
    date_label: str
    reading_minutes: int
    word_count: int
    slide_asset_path: str
    slide_points: list[str]
    source_links: list[str]
    updated_label: str
    related_articles: list[tuple[str, str]]


def article_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem


def render_markdown(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source_links = extract_source_links(source)
    return markdown.markdown(
        normalize_reference_section(source, source_links),
        extensions=["extra", "sane_lists"],
    )


def article_summary(md_path: Path) -> str:
    lines = [line.strip() for line in md_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    body_lines = [line for line in lines if not line.startswith("#")]
    cleaned_lines = [
        re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()
        for line in body_lines[:3]
    ]
    summary = re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()
    return summary[:170] + ("…" if len(summary) > 170 else "")


def article_slide_points(md_path: Path) -> list[str]:
    lines = [line.strip() for line in md_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    points: list[str] = []
    prioritized: list[str] = []
    fallback: list[str] = []
    for line in lines:
        if line.startswith("###"):
            cleaned = line.lstrip("#").strip()
            if cleaned:
                prioritized.append(cleaned)
            continue
        if line.startswith("##"):
            cleaned = line.lstrip("#").strip()
            if cleaned:
                prioritized.append(cleaned)
            continue
        if line.startswith("#"):
            continue
        cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip("` ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) < 8:
            continue
        target = prioritized if line.startswith(("-", "*")) or re.match(r"^\d+[\.\)]", line) else fallback
        target.append(cleaned)
    for pool in [prioritized, fallback]:
        for item in pool:
            compact = item[:28] + ("…" if len(item) > 28 else "")
            if compact in points:
                continue
            points.append(compact)
            if len(points) == 3:
                break
        if len(points) == 3:
            break
    return points or ["記事の要点を短時間でつかめる補足スライドです。"]


def article_section_labels(md_path: Path) -> list[str]:
    labels: list[str] = []
    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("##"):
            continue
        cleaned = stripped.lstrip("#").strip()
        if not cleaned or cleaned == "参考":
            continue
        labels.append(cleaned)
    return labels[:6]


def article_highlight_points(md_path: Path) -> list[str]:
    points: list[str] = []
    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            cleaned = stripped[2:].strip()
            if cleaned and len(cleaned) >= 6:
                points.append(cleaned[:46] + ("…" if len(cleaned) > 46 else ""))
        elif re.match(r"^\d+\.\s+", stripped):
            cleaned = re.sub(r"^\d+\.\s+", "", stripped).strip()
            if cleaned and len(cleaned) >= 6:
                points.append(cleaned[:46] + ("…" if len(cleaned) > 46 else ""))
        if len(points) >= 4:
            break
    if not points:
        points = article_slide_points(md_path)
    return points[:4]


def article_date_label(path: Path) -> str:
    match = DATE_PATTERN.match(path.stem)
    if not match:
        return "Undated"
    try:
        value = datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError:
        return match.group(1)
    return value.strftime("%Y.%m.%d")


def article_updated_label(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y.%m.%d")


def extract_source_links(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)>\"]+", text)
    deduped: list[str] = []
    for url in urls:
        normalized = url.rstrip(".,]")
        if normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


def normalize_reference_section(text: str, source_links: list[str]) -> str:
    lines = text.splitlines()
    result: list[str] = []
    in_reference = False
    seen_urls: list[str] = []
    reference_found = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") and "参考" in stripped:
            in_reference = True
            reference_found = True
            result.append(line)
            continue
        if in_reference and stripped.startswith("## ") and "参考" not in stripped:
            missing = [url for url in source_links if url not in seen_urls]
            for url in missing:
                result.append(f"- [{url}]({url})")
            in_reference = False
        if in_reference:
            linked_line, urls = normalize_reference_line(line)
            seen_urls.extend(url for url in urls if url not in seen_urls)
            result.append(linked_line)
            continue
        result.append(line)

    if in_reference:
        missing = [url for url in source_links if url not in seen_urls]
        for url in missing:
            result.append(f"- [{url}]({url})")
    elif not reference_found and source_links:
        result.extend(["", "## 参考", ""])
        for url in source_links:
            result.append(f"- [{url}]({url})")
    return "\n".join(result)


def normalize_reference_line(line: str) -> tuple[str, list[str]]:
    stripped = line.strip()
    if not stripped:
        return line, []
    markdown_match = re.match(r"^[-*]\s+\[([^\]]+)\]\((https?://[^)]+)\)\s*$", stripped)
    if markdown_match:
        label = markdown_match.group(1).strip()
        url = markdown_match.group(2).strip()
        return f"- [{label}]({url})", [url]
    url_match = re.search(r"https?://[^\s)>\"]+", stripped)
    if not url_match:
        return line, []
    url = url_match.group(0).rstrip(".,]")
    urls = [url]
    bullet_prefix = ""
    working = stripped
    if working.startswith("- "):
        bullet_prefix = "- "
        working = working[2:].strip()
    elif working.startswith("* "):
        bullet_prefix = "- "
        working = working[2:].strip()
    label = working.replace(url_match.group(0), "").strip()
    label = label.rstrip(":： ").strip()
    if not label:
        label = url
    return f"{bullet_prefix}[{label}]({url})", urls


def count_words(text: str) -> int:
    tokens = re.findall(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]+", text)
    return len(tokens)


def reading_minutes(word_count: int) -> int:
    return max(1, round(word_count / 520))


def wrap_svg_text(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False) or [text]


def render_svg_text_block(
    lines: list[str],
    *,
    x: int,
    y: int,
    size: int,
    line_height: int,
    fill: str,
    family: str,
    weight: str = "400",
) -> list[str]:
    parts: list[str] = []
    current_y = y
    for line in lines:
        parts.append(
            f'<text x="{x}" y="{current_y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(line)}</text>'
        )
        current_y += line_height
    return parts


def render_slide_illustration(group_slug: str) -> list[str]:
    if group_slug == "claude":
        return [
            '<rect x="1140" y="240" width="270" height="320" rx="34" fill="#1b2130" />',
            '<circle cx="1275" cy="322" r="88" fill="#f6efe4" />',
            '<path d="M1230 318 Q1275 270 1320 318 Q1310 378 1275 408 Q1240 378 1230 318" fill="#d6e5ff" />',
            '<rect x="1190" y="436" width="170" height="18" rx="9" fill="#f0f4f8" />',
            '<rect x="1190" y="468" width="126" height="18" rx="9" fill="#8395aa" />',
            '<circle cx="1356" cy="278" r="24" fill="#cde9df" />',
            '<path d="M1346 278 L1354 286 L1368 268" stroke="#0f766e" stroke-width="5" fill="none" stroke-linecap="round" />',
        ]
    if group_slug == "disaster_dx":
        return [
            '<rect x="1142" y="240" width="268" height="320" rx="30" fill="#182833" />',
            '<path d="M1188 478 L1240 386 L1284 430 L1326 344 L1364 478 Z" fill="#dbeafe" />',
            '<rect x="1190" y="500" width="174" height="16" rx="8" fill="#f8fafc" />',
            '<rect x="1190" y="532" width="132" height="16" rx="8" fill="#9fb8c9" />',
            '<circle cx="1228" cy="304" r="28" fill="#fde68a" />',
            '<path d="M1298 294 L1344 340" stroke="#f97316" stroke-width="10" stroke-linecap="round" />',
            '<path d="M1344 294 L1298 340" stroke="#f97316" stroke-width="10" stroke-linecap="round" />',
        ]
    if group_slug == "baby":
        return [
            '<circle cx="1270" cy="355" r="120" fill="#ffe8d5" />',
            '<circle cx="1270" cy="315" r="58" fill="#ffd3b8" />',
            '<circle cx="1248" cy="302" r="6" fill="#6f4e37" />',
            '<circle cx="1292" cy="302" r="6" fill="#6f4e37" />',
            '<path d="M1246 336 Q1270 352 1294 336" stroke="#6f4e37" stroke-width="6" fill="none" stroke-linecap="round" />',
            '<rect x="1170" y="380" width="200" height="150" rx="54" fill="#ffffff" stroke="#f1c9aa" />',
            '<circle cx="1210" cy="438" r="20" fill="#ffd9ec" />',
            '<circle cx="1330" cy="438" r="20" fill="#d7f0df" />',
            '<rect x="1206" y="548" width="128" height="18" rx="9" fill="#d8d5ce" />',
        ]
    if group_slug == "ai_practical":
        return [
            '<rect x="1145" y="238" width="250" height="320" rx="30" fill="#13212d" />',
            '<rect x="1182" y="282" width="176" height="106" rx="20" fill="#eff6ff" />',
            '<circle cx="1218" cy="335" r="16" fill="#1d4ed8" />',
            '<circle cx="1270" cy="318" r="16" fill="#0f766e" />',
            '<circle cx="1322" cy="350" r="16" fill="#b24d2d" />',
            '<path d="M1234 333 L1254 322 L1306 347" stroke="#13212d" stroke-width="5" fill="none" stroke-linecap="round" />',
            '<rect x="1182" y="418" width="176" height="28" rx="14" fill="#1f2e3a" />',
            '<rect x="1182" y="462" width="132" height="28" rx="14" fill="#2a4151" />',
            '<rect x="1182" y="506" width="94" height="28" rx="14" fill="#39566a" />',
        ]
    return [
        '<rect x="1160" y="240" width="250" height="320" rx="28" fill="#13212d" />',
        '<rect x="1200" y="280" width="170" height="220" rx="20" fill="#fffdf8" />',
        '<rect x="1226" y="320" width="118" height="14" rx="7" fill="#13212d" />',
        '<rect x="1226" y="354" width="86" height="14" rx="7" fill="#557086" />',
        '<rect x="1226" y="388" width="108" height="14" rx="7" fill="#557086" />',
        '<path d="M1236 442 L1270 470 L1334 406" stroke="#0f766e" stroke-width="10" fill="none" stroke-linecap="round" stroke-linejoin="round" />',
        '<circle cx="1360" cy="274" r="38" fill="#d9f3eb" />',
        '<path d="M1348 274 L1358 284 L1378 260" stroke="#0f766e" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round" />',
    ]


def render_slide_svg(group_label: str, article: Article) -> str:
    title_lines = wrap_svg_text(article.title, 18)[:2]
    summary_lines = wrap_svg_text(article.summary, 28)[:2]
    points = article.slide_points[:3]
    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">',
        f"<title>{html.escape(article.title)}</title>",
        f"<desc>{html.escape(article.summary)}</desc>",
        '<defs>',
        '<linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">',
        '<stop offset="0%" stop-color="#fff8ef" />',
        '<stop offset="55%" stop-color="#f4efe6" />',
        '<stop offset="100%" stop-color="#e6efe8" />',
        '</linearGradient>',
        '<linearGradient id="orb" x1="0%" x2="100%" y1="0%" y2="100%">',
        '<stop offset="0%" stop-color="#b24d2d" stop-opacity="0.28" />',
        '<stop offset="100%" stop-color="#0f766e" stop-opacity="0.18" />',
        '</linearGradient>',
        '</defs>',
        '<rect width="1600" height="900" fill="url(#bg)" />',
        '<circle cx="1310" cy="128" r="220" fill="url(#orb)" />',
        '<circle cx="1460" cy="720" r="180" fill="#d7e9f1" fill-opacity="0.75" />',
        '<rect x="70" y="70" width="1460" height="760" rx="42" fill="#fffdf8" fill-opacity="0.82" stroke="#d7cec3" />',
        '<rect x="110" y="116" width="150" height="38" rx="19" fill="#13212d" />',
        f'<text x="142" y="141" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="18" font-weight="700" letter-spacing="2" fill="#fffdf8">{html.escape(group_label.upper())}</text>',
        f'<text x="292" y="142" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="22" fill="#0f766e">{html.escape(article.date_label)} / {article.reading_minutes} min read</text>',
        '<text x="110" y="198" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="20" letter-spacing="3" fill="#6b6259">ARTICLE SNAPSHOT</text>',
    ]
    svg_parts.extend(
        render_svg_text_block(
            title_lines,
            x=110,
            y=294,
            size=62,
            line_height=76,
            fill="#13212d",
            family="Iowan Old Style, Hiragino Mincho ProN, Yu Mincho, serif",
            weight="700",
        )
    )
    svg_parts.extend(
        render_svg_text_block(
            summary_lines,
            x=110,
            y=466,
            size=28,
            line_height=40,
            fill="#4d5a64",
            family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif",
        )
    )
    svg_parts.append('<text x="110" y="578" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="20" letter-spacing="3" fill="#6b6259">POINTS</text>')
    card_y = 650
    for index, point in enumerate(points, start=1):
        top = card_y + (index - 1) * 72
        svg_parts.extend(
            [
                f'<rect x="110" y="{top - 34}" width="820" height="54" rx="18" fill="#f8f3ea" stroke="#e6ddd0" />',
                f'<circle cx="148" cy="{top - 7}" r="15" fill="#13212d" />',
                f'<text x="143" y="{top - 1}" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="16" font-weight="700" fill="#ffffff">{index}</text>',
                f'<text x="182" y="{top}" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="26" fill="#13212d">{html.escape(point)}</text>',
            ]
        )
    svg_parts.extend(
        [
            '<rect x="1040" y="168" width="430" height="564" rx="34" fill="#13212d" />',
            '<rect x="1082" y="212" width="346" height="478" rx="28" fill="#fffaf2" />',
            f'<text x="1108" y="626" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="18" letter-spacing="2" fill="#6b6259">{html.escape(group_label)} / Visual Summary</text>',
            '<text x="1108" y="662" font-family="Avenir Next, Hiragino Sans, Yu Gothic, sans-serif" font-size="24" font-weight="700" fill="#13212d">読む前に全体像をつかむ</text>',
        ]
    )
    group_slug = article.slide_asset_path.split("/")[2]
    svg_parts.extend(render_slide_illustration(group_slug))
    svg_parts.append("</svg>")
    return "".join(svg_parts)


def load_publish_groups() -> list[TopicGroup]:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    groups: list[TopicGroup] = []
    for item in raw.get("topics", []):
        if not item.get("publish", True):
            continue
        groups.append(
            TopicGroup(
                source_group=str(item["output_dir"]),
                slug=str(item["id"]),
                label=str(item["label"]),
                description=str(item.get("description") or ""),
                target_reader=str(item.get("target_reader") or ""),
                tone=str(item.get("tone") or ""),
                style_guide=dict(item.get("style_guide") or {}),
            )
        )
    return groups


def build_series_path(articles: list[Article]) -> str:
    ordered = sorted(articles, key=lambda article: article.anchor)
    parts = [
        f'<li><a href="#{html.escape(article.anchor)}">{html.escape(article.date_label)} | {html.escape(article.title)}</a></li>'
        for article in ordered[:5]
    ]
    return "".join(parts)


def token_set(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]{2,}", text)}


def build_related_articles(articles: list[Article]) -> None:
    article_tokens = {
        article.anchor: token_set(f"{article.title} {article.summary}")
        for article in articles
    }
    for article in articles:
        base = article_tokens[article.anchor]
        scored: list[tuple[int, Article]] = []
        for candidate in articles:
            if candidate.anchor == article.anchor:
                continue
            overlap = len(base & article_tokens[candidate.anchor])
            scored.append((overlap, candidate))
        scored.sort(key=lambda item: (item[0], item[1].date_label), reverse=True)
        article.related_articles = [(item.anchor, item.title) for _, item in scored[:3] if _ > 0]


def build_infographic_panel(group: dict[str, object], article: Article) -> str:
    stat_items = [
        ("Reading", f"{article.reading_minutes} min"),
        ("Sections", str(max(1, len(article.section_labels)))),
        ("Sources", str(len(article.source_links))),
        ("Updated", article.updated_label),
    ]
    stats = "".join(
        f"""
<div class="info-stat">
  <span>{html.escape(label)}</span>
  <strong>{html.escape(value)}</strong>
</div>
"""
        for label, value in stat_items
    )
    section_pills = "".join(
        f'<a class="section-pill" href="#{html.escape(article.anchor)}-section-{index + 1}">{html.escape(label)}</a>'
        for index, label in enumerate(article.section_labels)
    ) or '<span class="section-pill muted">本文の構成は本文中で確認</span>'
    highlights = "".join(
        f"""
<div class="insight-card">
  <div class="insight-index">{index}</div>
  <p>{html.escape(point)}</p>
</div>
"""
        for index, point in enumerate(article.highlight_points, start=1)
    )
    return f"""
<section class="infographic-panel">
  <div class="info-hero">
    <div class="info-copy">
      <div class="info-kicker">{html.escape(str(group['label']))} / ARTICLE MAP</div>
      <h3>{html.escape(article.title)}</h3>
      <p>{html.escape(article.summary)}</p>
    </div>
    <div class="info-stats">
      {stats}
    </div>
  </div>
  <div class="insight-grid">
    {highlights}
  </div>
  <div class="section-pills">
    {section_pills}
  </div>
</section>
"""


def add_section_anchors(rendered_html: str, article: Article) -> str:
    output = rendered_html
    for index, label in enumerate(article.section_labels, start=1):
        pattern = f"<h2>{html.escape(label)}</h2>"
        replacement = f'<h2 id="{html.escape(article.anchor)}-section-{index}">{html.escape(label)}</h2>'
        output = output.replace(pattern, replacement, 1)
    return output


def page_shell(title: str, body: str, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="生活と実務の境界にあるテーマを、読みやすく探しやすく届ける静的ブログ">
  {extra_head}
  <style>
    :root {{
      --bg: #f4efe6;
      --bg-soft: #fbf7f0;
      --surface: rgba(255, 251, 245, 0.84);
      --surface-strong: rgba(255, 255, 255, 0.9);
      --ink: #13212d;
      --muted: #5f615e;
      --line: rgba(19, 33, 45, 0.09);
      --accent: #b24d2d;
      --accent-2: #0f766e;
      --accent-3: #1d4ed8;
      --shadow: 0 22px 60px rgba(19, 33, 45, 0.08);
      --shadow-strong: 0 30px 90px rgba(19, 33, 45, 0.12);
      --radius-xl: 30px;
      --radius-lg: 22px;
      --radius-md: 16px;
      --sans: "Avenir Next", "Hiragino Sans", "Yu Gothic", sans-serif;
      --serif: "Iowan Old Style", "Hiragino Mincho ProN", "Yu Mincho", serif;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 8% 8%, rgba(254, 215, 170, 0.78), transparent 28%),
        radial-gradient(circle at 92% 12%, rgba(191, 219, 254, 0.72), transparent 26%),
        radial-gradient(circle at 60% 100%, rgba(134, 239, 172, 0.24), transparent 20%),
        linear-gradient(180deg, #fffdf9 0%, var(--bg-soft) 40%, var(--bg) 100%);
      font-family: var(--sans);
      -webkit-font-smoothing: antialiased;
    }}
    .skip-link {{
      position: absolute;
      left: 12px;
      top: -48px;
      padding: 10px 14px;
      border-radius: 999px;
      background: var(--ink);
      color: #fff;
      z-index: 50;
      transition: top .2s ease;
    }}
    .skip-link:focus {{
      top: 12px;
    }}
    a {{
      color: inherit;
      text-decoration: none;
    }}
    img {{
      max-width: 100%;
      display: block;
    }}
    .shell {{
      width: min(1200px, calc(100vw - 20px));
      margin: 0 auto;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(16px);
      background: rgba(251, 247, 240, 0.72);
      border-bottom: 1px solid rgba(19, 33, 45, 0.06);
    }}
    .topbar-inner {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 58px;
      padding: 8px 0;
      flex-wrap: wrap;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 0.92rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .brand-mark {{
      width: 14px;
      height: 14px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 0 0 8px rgba(178, 77, 45, 0.09);
    }}
    .top-links {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: nowrap;
      justify-content: start;
      overflow-x: auto;
      width: 100%;
      padding-bottom: 2px;
      scrollbar-width: none;
    }}
    .top-links::-webkit-scrollbar {{
      display: none;
    }}
    .top-links a {{
      padding: 10px 12px;
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.9rem;
      white-space: nowrap;
    }}
    .top-links a.active {{
      background: rgba(19,33,45,0.92);
      color: #fff;
    }}
    .top-links a:hover {{
      background: rgba(255,255,255,0.72);
      color: var(--ink);
    }}
    .hero {{
      padding: 20px 0 18px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
      align-items: stretch;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .hero-main {{
      position: relative;
      overflow: hidden;
      padding: 22px;
      min-height: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .hero-main::after {{
      content: "";
      position: absolute;
      right: -70px;
      bottom: -70px;
      width: 240px;
      height: 240px;
      border-radius: 999px;
      background: linear-gradient(135deg, rgba(178,77,45,.16), rgba(29,78,216,.08), rgba(15,118,110,.15));
      filter: blur(2px);
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 0.74rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .eyebrow::before {{
      content: "";
      width: 24px;
      height: 1px;
      background: var(--accent);
    }}
    .hero-main h1 {{
      margin: 14px 0 12px;
      max-width: none;
      font-family: var(--serif);
      font-size: clamp(2.4rem, 11vw, 4rem);
      line-height: 0.98;
      letter-spacing: -0.045em;
    }}
    .hero-copy {{
      max-width: none;
      font-size: 0.98rem;
      line-height: 1.82;
      color: var(--ink);
      position: relative;
      z-index: 1;
    }}
    .topic-pills {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 22px;
      position: relative;
      z-index: 1;
    }}
    .topic-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.74);
      border: 1px solid rgba(19,33,45,.08);
      font-size: 0.9rem;
    }}
    .hero-side {{
      padding: 18px;
      display: grid;
      grid-template-rows: auto auto 1fr;
      gap: 12px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric {{
      border-radius: var(--radius-md);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.64);
      padding: 14px;
    }}
    .metric strong {{
      display: block;
      font-size: 1.55rem;
      margin-bottom: 6px;
      font-family: var(--serif);
    }}
    .search-panel {{
      border-radius: 20px;
      border: 1px solid var(--line);
      padding: 14px;
      background: rgba(255,255,255,0.7);
    }}
    .search-panel label {{
      display: block;
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .search-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 10px 8px 14px;
      border-radius: 999px;
      background: rgba(244, 239, 230, 0.9);
      border: 1px solid rgba(19,33,45,.08);
    }}
    .search-row input {{
      width: 100%;
      border: 0;
      background: transparent;
      color: var(--ink);
      font: inherit;
      outline: none;
    }}
    .search-chip {{
      white-space: nowrap;
      border-radius: 999px;
      padding: 8px 12px;
      background: var(--ink);
      color: #fff;
      font-size: 0.87rem;
    }}
    .highlight-list {{
      display: grid;
      gap: 10px;
    }}
    .highlight-card {{
      display: block;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      transition: transform .24s ease, box-shadow .24s ease;
    }}
    .highlight-card:hover,
    .category-card:hover,
    .article-card:hover,
    .mini-card:hover {{
      transform: translateY(-2px);
      box-shadow: var(--shadow-strong);
    }}
    .highlight-card span {{
      display: block;
      color: var(--muted);
      font-size: 0.84rem;
      margin-bottom: 6px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .quick-links {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .quick-links a {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      color: var(--ink);
      font-size: 0.9rem;
    }}
    .section {{
      padding: 12px 0 34px;
    }}
    .section-head {{
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 14px;
    }}
    .section-head h2 {{
      margin: 0;
      font-family: var(--serif);
      font-size: clamp(1.55rem, 7vw, 2.3rem);
      line-height: 1.06;
      letter-spacing: -0.03em;
    }}
    .section-head p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.85;
      max-width: 42rem;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .mini-card {{
      padding: 18px;
      border-radius: var(--radius-lg);
      background: rgba(255,255,255,0.78);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      transition: transform .24s ease, box-shadow .24s ease;
    }}
    .mini-card strong {{
      display: block;
      margin: 10px 0 8px;
      font-size: 1.08rem;
      line-height: 1.45;
    }}
    .mini-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.75;
      font-size: 0.94rem;
    }}
    .mini-meta {{
      font-size: 0.78rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent-2);
    }}
    .category-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .category-card {{
      position: relative;
      overflow: hidden;
      padding: 20px;
      min-height: 0;
      transition: transform .24s ease, box-shadow .24s ease;
    }}
    .category-card::after {{
      content: "";
      position: absolute;
      right: -30px;
      top: -30px;
      width: 160px;
      height: 160px;
      border-radius: 999px;
      background: linear-gradient(135deg, rgba(178,77,45,.16), rgba(15,118,110,.08));
    }}
    .category-card h3 {{
      position: relative;
      z-index: 1;
      margin: 16px 0 10px;
      font-size: 1.55rem;
      font-family: var(--serif);
    }}
    .category-card p,
    .category-card ul {{
      position: relative;
      z-index: 1;
    }}
    .category-card p {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.8;
    }}
    .category-card ul {{
      margin: 0 0 16px;
      padding-left: 1.05rem;
      line-height: 1.75;
      color: var(--ink);
    }}
    .category-meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
      font-size: 0.85rem;
      color: var(--muted);
    }}
    .filter-row {{
      display: flex;
      justify-content: flex-start;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .filter-pills {{
      display: flex;
      gap: 8px;
      flex-wrap: nowrap;
      overflow-x: auto;
      width: 100%;
      padding-bottom: 2px;
      scrollbar-width: none;
    }}
    .filter-pills::-webkit-scrollbar {{
      display: none;
    }}
    .filter-pill {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      color: var(--ink);
      border-radius: 999px;
      padding: 10px 12px;
      cursor: pointer;
      font: inherit;
      white-space: nowrap;
    }}
    .filter-pill.active {{
      background: var(--ink);
      color: #fff;
      border-color: var(--ink);
    }}
    .article-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .article-card {{
      display: block;
      padding: 18px;
      border-radius: var(--radius-lg);
      background: rgba(255,255,255,0.78);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      transition: transform .24s ease, box-shadow .24s ease, border-color .24s ease;
    }}
    .article-card .slide-thumb {{
      margin: -18px -18px 16px;
      aspect-ratio: 16 / 9;
      overflow: hidden;
      border-radius: 18px 18px 14px 14px;
      border-bottom: 1px solid var(--line);
      background: #f8f3ea;
    }}
    .article-card .slide-thumb img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .article-card:hover {{
      border-color: rgba(178,77,45,.24);
    }}
    .article-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .article-meta {{
      font-size: 0.78rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .article-card h3 {{
      margin: 0 0 10px;
      font-size: 1.12rem;
      line-height: 1.38;
    }}
    .article-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.82;
    }}
    .article-bottom {{
      margin-top: 16px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .page-hero {{
      padding: 18px 0 12px;
    }}
    .breadcrumbs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 10px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .breadcrumbs a {{
      color: var(--muted);
    }}
    .page-layout {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
      padding: 8px 0 42px;
      min-width: 0;
    }}
    .side-stack {{
      display: grid;
      gap: 12px;
      position: static;
      align-self: start;
    }}
    .side-card {{
      padding: 18px;
      border-radius: var(--radius-lg);
      background: rgba(255,255,255,0.78);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }}
    .side-card h2,
    .side-card h3 {{
      margin: 0 0 12px;
      font-size: 1.15rem;
    }}
    .side-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.8;
      font-size: 0.95rem;
    }}
    .side-card nav a {{
      display: block;
      padding: 10px 0;
      border-top: 1px solid var(--line);
      line-height: 1.6;
    }}
    .side-card ul {{
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    .side-card li + li {{
      margin-top: 8px;
    }}
    .side-card li a {{
      display: block;
      padding: 10px 0;
      border-top: 1px solid var(--line);
      line-height: 1.6;
    }}
    .page-main {{
      display: grid;
      gap: 18px;
      min-width: 0;
    }}
    .article-panel {{
      padding: 20px;
      border-radius: var(--radius-xl);
      background: rgba(255,255,255,0.8);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      min-width: 0;
      overflow: hidden;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(15,118,110,.16);
      color: var(--accent-2);
      background: rgba(15,118,110,.07);
      font-size: 0.82rem;
      margin-bottom: 12px;
    }}
    .article-panel header {{
      margin-bottom: 18px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }}
    .infographic-panel {{
      margin: 0 0 18px;
      padding: 16px;
      border-radius: 22px;
      background:
        linear-gradient(135deg, rgba(255,255,255,0.96), rgba(248,243,234,0.9)),
        radial-gradient(circle at top right, rgba(29,78,216,.08), transparent 30%);
      border: 1px solid rgba(19,33,45,.08);
      box-shadow: var(--shadow);
    }}
    .info-hero {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .info-kicker {{
      font-size: 0.76rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--accent-2);
      margin-bottom: 10px;
    }}
    .info-copy h3 {{
      margin: 0 0 8px;
      font-size: 1.2rem;
      line-height: 1.35;
    }}
    .info-copy p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.8;
    }}
    .info-stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .info-stat {{
      padding: 12px;
      border-radius: 16px;
      background: rgba(255,255,255,0.88);
      border: 1px solid var(--line);
    }}
    .info-stat span {{
      display: block;
      color: var(--muted);
      font-size: 0.74rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .info-stat strong {{
      display: block;
      font-size: 1rem;
      line-height: 1.25;
    }}
    .insight-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
      margin: 0 0 14px;
    }}
    .insight-card {{
      display: grid;
      grid-template-columns: 34px 1fr;
      gap: 10px;
      align-items: start;
      padding: 12px;
      border-radius: 16px;
      background: rgba(255,255,255,0.8);
      border: 1px solid var(--line);
    }}
    .insight-index {{
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 999px;
      background: var(--ink);
      color: #fff;
      font-size: 0.9rem;
      font-weight: 700;
    }}
    .insight-card p {{
      margin: 0;
      line-height: 1.7;
    }}
    .section-pills {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .section-pill {{
      display: inline-flex;
      align-items: center;
      padding: 9px 11px;
      border-radius: 999px;
      background: rgba(19,33,45,0.06);
      border: 1px solid rgba(19,33,45,0.08);
      font-size: 0.86rem;
      line-height: 1.4;
    }}
    .section-pill.muted {{
      color: var(--muted);
    }}
    .article-panel h2 {{
      margin: 0 0 12px;
      font-family: var(--serif);
      font-size: clamp(1.5rem, 7vw, 2.1rem);
      line-height: 1.15;
      letter-spacing: -0.03em;
    }}
    .article-panel .article-body p,
    .article-panel .article-body li {{
      font-size: 0.98rem;
      line-height: 1.88;
      color: #24313c;
      overflow-wrap: anywhere;
    }}
    .article-panel .article-body {{
      min-width: 0;
    }}
    .article-panel .article-body h1 {{
      display: none;
    }}
    .article-panel .article-body h2,
    .article-panel .article-body h3 {{
      margin-top: 2rem;
      font-family: var(--serif);
      font-size: 1.35rem;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }}
    .article-panel .article-body ul,
    .article-panel .article-body ol {{
      padding-left: 1.25rem;
    }}
    .article-panel .article-body a {{
      color: var(--accent-3);
      text-decoration: underline;
      text-underline-offset: 0.14em;
      overflow-wrap: anywhere;
    }}
    .article-panel .article-body img,
    .article-panel .article-body svg,
    .article-panel .article-body iframe {{
      max-width: 100%;
      height: auto;
      border-radius: 16px;
    }}
    .article-panel .article-body table {{
      display: block;
      width: 100%;
      max-width: 100%;
      overflow-x: auto;
      border-collapse: collapse;
      -webkit-overflow-scrolling: touch;
    }}
    .article-panel .article-body th,
    .article-panel .article-body td {{
      border: 1px solid var(--line);
      padding: 10px 12px;
      vertical-align: top;
      min-width: 120px;
    }}
    .article-panel .article-body pre {{
      max-width: 100%;
      overflow-x: auto;
      padding: 14px;
      border-radius: 16px;
      background: #18232d;
      color: #f8fafc;
      -webkit-overflow-scrolling: touch;
    }}
    .article-panel .article-body code {{
      overflow-wrap: anywhere;
    }}
    .article-panel .article-body blockquote {{
      margin: 1.6rem 0;
      padding: 0.2rem 1rem;
      border-left: 3px solid rgba(178,77,45,.42);
      color: var(--muted);
      background: rgba(244,239,230,.64);
    }}
    .source-links {{
      margin-top: 22px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
    }}
    .source-links h3 {{
      margin: 0 0 10px;
      font-size: 1rem;
    }}
    .source-links ul {{
      margin: 0;
      padding-left: 1.1rem;
    }}
    .source-links li + li {{
      margin-top: 8px;
    }}
    .source-links a {{
      color: var(--accent-3);
      text-decoration: underline;
      text-underline-offset: 0.14em;
      overflow-wrap: anywhere;
    }}
    .footer {{
      padding: 0 0 52px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .hide {{
      display: none !important;
    }}
    @media (min-width: 760px) {{
      .shell {{
        width: min(1200px, calc(100vw - 32px));
      }}
      .topbar-inner {{
        gap: 18px;
        min-height: 62px;
        padding: 10px 0;
        flex-wrap: nowrap;
      }}
      .top-links {{
        width: auto;
        justify-content: end;
        flex-wrap: wrap;
        overflow: visible;
      }}
      .hero {{
        padding: 28px 0 22px;
      }}
      .hero-grid,
      .page-layout {{
        grid-template-columns: 1fr;
      }}
      .hero-main,
      .hero-side,
      .side-card,
      .article-card,
      .mini-card,
      .category-card,
      .article-panel {{
        padding: 24px;
      }}
      .hero-main h1 {{
        font-size: clamp(2.8rem, 7vw, 4.8rem);
      }}
      .hero-copy {{
        font-size: 1.02rem;
        line-height: 1.9;
      }}
      .section {{
        padding: 16px 0 44px;
      }}
      .section-head {{
        margin-bottom: 18px;
      }}
      .mini-grid,
      .category-grid,
      .article-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 16px;
      }}
      .info-hero {{
        grid-template-columns: 1.3fr 0.9fr;
      }}
      .insight-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .filter-pills {{
        width: auto;
        overflow: visible;
        flex-wrap: wrap;
      }}
    }}
    @media (min-width: 1040px) {{
      .hero-grid {{
        grid-template-columns: 1.35fr 0.95fr;
        gap: 22px;
      }}
      .page-layout {{
        grid-template-columns: 320px minmax(0, 1fr);
        gap: 22px;
        padding: 12px 0 70px;
      }}
      .side-stack {{
        position: sticky;
        top: 84px;
      }}
      .hero-main {{
        min-height: 390px;
        padding: 34px;
      }}
      .hero-side {{
        padding: 26px;
      }}
      .hero-main h1 {{
        max-width: 10ch;
        font-size: clamp(3rem, 6vw, 6rem);
        line-height: 0.94;
      }}
      .hero-copy {{
        max-width: 42rem;
        font-size: 1.06rem;
        line-height: 1.95;
      }}
      .mini-grid {{
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 420px) {{
      .shell {{
        width: calc(100vw - 16px);
      }}
    }}
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content">本文へ移動</a>
  {body}
</body>
</html>
"""


def build_topbar(groups: list[dict[str, object]], base_prefix: str = "./", current_slug: str = "") -> str:
    link_parts: list[str] = []
    for group in groups:
        class_attr = ' class="active"' if group["slug"] == current_slug else ""
        link_parts.append(
            f'<a href="{base_prefix}{group["slug"]}/"{class_attr}>{html.escape(str(group["label"]))}</a>'
        )
    links = "".join(link_parts)
    return f"""
<div class="topbar">
  <div class="shell topbar-inner">
    <a class="brand" href="{base_prefix}">
      <span class="brand-mark"></span>
      <span>{SITE_TITLE}</span>
    </a>
    <div class="top-links">
      {links}
      <a href="{REPO_URL}" target="_blank" rel="noreferrer">GitHub</a>
    </div>
  </div>
</div>
"""


def build_home_featured(groups: list[dict[str, object]]) -> str:
    cards: list[str] = []
    for group in groups:
        articles = list(group["articles"])
        if not articles:
            continue
        article = articles[0]
        cards.append(
            f"""
<a class="mini-card" href="./{group['slug']}/#{article.anchor}">
  <div class="mini-meta">{html.escape(str(group['label']))}</div>
  <strong>{html.escape(article.title)}</strong>
  <p>{html.escape(article.summary)}</p>
</a>
"""
        )
    return "".join(cards)


def build_category_card(group: dict[str, object]) -> str:
    articles = list(group["articles"])
    samples = "".join(
        f"<li>{html.escape(article.title)}</li>"
        for article in articles[:3]
    )
    latest = articles[0].date_label if articles else "Undated"
    return f"""
<a class="category-card panel" href="./{group['slug']}/">
  <div class="eyebrow">{html.escape(str(group['label']))}</div>
  <h3>{html.escape(str(group['label']))}</h3>
  <p>{html.escape(str(group['description']))}</p>
  <ul>{samples}</ul>
  <div class="category-meta">
    <span>{len(articles)} articles</span>
    <span>latest {html.escape(str(latest))}</span>
  </div>
</a>
"""


def build_article_card(group: dict[str, object], article: Article) -> str:
    search_text = f"{group['label']} {article.title} {article.summary}"
    return f"""
<a class="article-card" data-search-card data-group="{html.escape(str(group['slug']))}" data-search="{html.escape(search_text)}" href="./{group['slug']}/#{article.anchor}">
  <div class="slide-thumb">
    <img src="./{html.escape(article.slide_asset_path)}" alt="{html.escape(article.title)} の補足スライド">
  </div>
  <div class="article-top">
    <div class="article-meta">{html.escape(str(group['label']))}</div>
    <div class="article-meta">{html.escape(article.date_label)}</div>
  </div>
  <h3>{html.escape(article.title)}</h3>
  <p>{html.escape(article.summary)}</p>
  <div class="article-bottom">
    <span>{article.word_count} words</span>
    <span>{article.reading_minutes} min read</span>
  </div>
</a>
"""


def build_index(groups: list[dict[str, object]]) -> str:
    stats_count = sum(len(group["articles"]) for group in groups)
    topic_labels = " / ".join(str(group["label"]) for group in groups)
    latest_date = max(
        (article.date_label for group in groups for article in group["articles"]),
        default="Undated",
    )
    pills = "".join(
        f'<a class="topic-pill" href="./{group["slug"]}/">{html.escape(str(group["label"]))}</a>'
        for group in groups
    )
    filter_pills = "".join(
        f'<button class="filter-pill" type="button" data-filter="{html.escape(str(group["slug"]))}">{html.escape(str(group["label"]))}</button>'
        for group in groups
    )
    body = f"""
{build_topbar(groups)}
<main class="shell" id="main-content">
  <section class="hero">
    <div class="hero-grid">
      <div class="hero-main panel">
        <div>
          <div class="eyebrow">Independent Editorial System</div>
          <h1>読む理由がある。<br>また戻る理由もある。</h1>
          <p class="hero-copy">このサイトは、{html.escape(topic_labels)}を軸に、実務や生活で次の判断に使える記事を蓄積するための編集アーカイブです。単発の話題よりも、継続して追う意味がある論点を見つけやすい導線へ整えています。</p>
          <div class="topic-pills">{pills}</div>
        </div>
      </div>
      <aside class="hero-side panel">
        <div class="metric-grid">
          <div class="metric">
            <strong>{len(groups)}</strong>
            <span>collections</span>
          </div>
          <div class="metric">
            <strong>{stats_count}</strong>
            <span>articles</span>
          </div>
          <div class="metric">
            <strong>{latest_date}</strong>
            <span>latest update</span>
          </div>
          <div class="metric">
            <strong>4h</strong>
            <span>automation cadence</span>
          </div>
        </div>
        <div class="search-panel">
          <label for="searchInput">Search articles</label>
          <div class="search-row">
            <input id="searchInput" type="search" placeholder="タイトルやテーマで検索">
            <span class="search-chip" id="resultCount">全{stats_count}本</span>
          </div>
        </div>
        <div class="highlight-list">
          <a class="highlight-card" href="#collections">
            <span>Browse</span>
            カテゴリから入って、まとめて読む
          </a>
          <a class="highlight-card" href="#latest">
            <span>Latest</span>
            最新記事から今の論点をつかむ
          </a>
        </div>
        <div class="quick-links">
          <a href="#collections">カテゴリ一覧</a>
          <a href="#latest">全記事一覧</a>
        </div>
      </aside>
    </div>
  </section>

  <section class="section">
    <div class="section-head">
      <div>
        <div class="eyebrow">Featured</div>
        <h2>各カテゴリの最新記事</h2>
      </div>
      <p>入口で迷わないよう、まずはテーマごとの最新1本を前面に出しています。新着を見れば、このサイトが今どこに注目しているかがわかります。</p>
    </div>
    <div class="mini-grid">
      {build_home_featured(groups)}
    </div>
  </section>

  <section class="section" id="collections">
    <div class="section-head">
      <div>
        <div class="eyebrow">Collections</div>
        <h2>カテゴリごとの世界観を分ける</h2>
      </div>
      <p>生活領域と実務領域が混ざっても読者が迷わないよう、カテゴリ単位で温度感と期待値を揃えています。</p>
    </div>
    <div class="category-grid">
      {''.join(build_category_card(group) for group in groups)}
    </div>
  </section>

  <section class="section" id="latest">
    <div class="section-head">
      <div>
        <div class="eyebrow">Article Index</div>
        <h2>探しやすい一覧</h2>
      </div>
      <p>検索とカテゴリフィルタで絞り込めます。カードから該当カテゴリの本文位置へそのまま移動できます。</p>
    </div>
    <div class="filter-row">
      <div class="filter-pills">
        <button class="filter-pill active" type="button" data-filter="all">All</button>
        {filter_pills}
      </div>
    </div>
    <div class="article-grid" id="articleGrid">
      {''.join(build_article_card(group, article) for group in groups for article in group['articles'])}
    </div>
  </section>

  <div class="footer">Built from Markdown content and published as a static archive. Repository: <a href="{REPO_URL}" target="_blank" rel="noreferrer">zukkiii324/self-research</a></div>
</main>
<script>
const searchInput = document.getElementById('searchInput');
const resultCount = document.getElementById('resultCount');
const cards = Array.from(document.querySelectorAll('[data-search-card]'));
const filters = Array.from(document.querySelectorAll('[data-filter]'));
let activeFilter = 'all';

function refreshCards() {{
  const q = (searchInput?.value || '').trim().toLowerCase();
  let visible = 0;
  cards.forEach((card) => {{
    const hay = (card.dataset.search || '').toLowerCase();
    const group = card.dataset.group || '';
    const matchesFilter = activeFilter === 'all' || group === activeFilter;
    const matchesSearch = !q || hay.includes(q);
    const show = matchesFilter && matchesSearch;
    card.classList.toggle('hide', !show);
    if (show) visible += 1;
  }});
  if (resultCount) {{
    resultCount.textContent = `${{visible}}件`;
  }}
}}

searchInput?.addEventListener('input', refreshCards);
filters.forEach((button) => {{
  button.addEventListener('click', () => {{
    activeFilter = button.dataset.filter || 'all';
    filters.forEach((item) => item.classList.toggle('active', item === button));
    refreshCards();
  }});
}});
refreshCards();
</script>
"""
    return page_shell("Editorial Playground", body)


def build_group_page(group: dict[str, object], groups: list[dict[str, object]]) -> str:
    links = "".join(
        f'<a href="#{html.escape(article.anchor)}">{html.escape(article.title)}</a>'
        for article in group["articles"]
    )
    articles = "".join(
        f"""
<article id="{html.escape(article.anchor)}" class="article-panel">
  <div class="tag">{html.escape(str(group['label']))}</div>
  <header>
    <h2>{html.escape(article.title)}</h2>
    <div class="article-bottom">
      <span>{html.escape(article.date_label)}</span>
      <span>updated {html.escape(article.updated_label)}</span>
      <span>{article.word_count} words</span>
      <span>{article.reading_minutes} min read</span>
    </div>
  </header>
  {build_infographic_panel(group, article)}
  <div class="article-body">{article.rendered}</div>
  <div class="source-links">
    <h3>関連記事</h3>
    <ul>{"".join(f'<li><a href="#{html.escape(anchor)}">{html.escape(title)}</a></li>' for anchor, title in article.related_articles) or "<li>同カテゴリ内で近い記事は準備中です。</li>"}</ul>
  </div>
</article>
"""
        for article in group["articles"]
    )
    other_groups = "".join(
        f'<li><a href="../{html.escape(str(other["slug"]))}/">{html.escape(str(other["label"]))}</a></li>'
        for other in groups
        if other["slug"] != group["slug"]
    )
    body = f"""
{build_topbar(groups, base_prefix="../", current_slug=str(group["slug"]))}
<main class="shell" id="main-content">
  <section class="page-hero">
    <div class="hero-grid">
      <div class="hero-main panel" style="min-height:300px;">
        <div>
          <div class="breadcrumbs"><a href="../">Home</a><span>/</span><span>{html.escape(str(group['label']))}</span></div>
          <div class="eyebrow">Collection</div>
          <h1>{html.escape(str(group['label']))}</h1>
          <p class="hero-copy">{html.escape(str(group['description']))}</p>
          <div class="topic-pills">
            <span class="topic-pill">for {html.escape(str(group['target_reader']))}</span>
            <span class="topic-pill">{html.escape(str(group['tone']))}</span>
            <span class="topic-pill">{len(group['articles'])} articles</span>
          </div>
        </div>
      </div>
      <aside class="hero-side panel">
        <div class="highlight-list">
          <a class="highlight-card" href="../">
            <span>Home</span>
            トップページへ戻る
          </a>
          <a class="highlight-card" href="#article-list">
            <span>Index</span>
            このカテゴリの記事一覧を見る
          </a>
        </div>
      </aside>
    </div>
  </section>
  <section class="page-layout">
    <aside class="side-stack">
      <div class="side-card">
        <h2>このカテゴリについて</h2>
        <p>{html.escape(str(group['description']))}</p>
      </div>
      <div class="side-card">
        <h3>この順で読む</h3>
        <ul>{build_series_path(list(group["articles"]))}</ul>
      </div>
      <div class="side-card">
        <h3>ほかのカテゴリ</h3>
        <ul>{other_groups}</ul>
      </div>
      <div class="side-card" id="article-list">
        <h3>記事一覧</h3>
        <nav>{links}</nav>
      </div>
    </aside>
    <div class="page-main">
      {articles}
    </div>
  </section>
  <div class="footer">Category archive: {html.escape(str(group['label']))} | Repository: <a href="{REPO_URL}" target="_blank" rel="noreferrer">zukkiii324/self-research</a></div>
</main>
"""
    return page_shell(str(group["label"]), body)


def collect_groups(content_root: Path, out_root: Path) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for topic in load_publish_groups():
        group_dir = content_root / topic.source_group
        if not group_dir.exists():
            continue
        articles: list[Article] = []
        for md_path in sorted(group_dir.glob("*.md"), reverse=True):
            if md_path.name.lower().startswith("readme"):
                continue
            text = md_path.read_text(encoding="utf-8")
            words = count_words(text)
            points = article_slide_points(md_path)
            slide_dir = out_root / "assets" / "slides" / topic.slug
            slide_dir.mkdir(parents=True, exist_ok=True)
            slide_asset_path = f"assets/slides/{topic.slug}/{md_path.stem}.svg"
            article = Article(
                anchor=md_path.stem,
                title=article_title(md_path),
                summary=article_summary(md_path),
                rendered="",
                section_labels=article_section_labels(md_path),
                highlight_points=article_highlight_points(md_path),
                date_label=article_date_label(md_path),
                updated_label=article_updated_label(md_path),
                reading_minutes=reading_minutes(words),
                word_count=words,
                slide_asset_path=slide_asset_path,
                slide_points=points,
                source_links=extract_source_links(text),
                related_articles=[],
            )
            article.rendered = add_section_anchors(render_markdown(md_path), article)
            slide_svg = render_slide_svg(topic.label, article)
            (slide_dir / f"{md_path.stem}.svg").write_text(slide_svg, encoding="utf-8")
            articles.append(
                article
            )
        if not articles:
            continue
        build_related_articles(articles)
        groups.append(
            {
                "slug": topic.slug,
                "label": topic.label,
                "description": topic.description,
                "target_reader": topic.target_reader,
                "tone": topic.tone,
                "style_guide": topic.style_guide,
                "articles": articles,
            }
        )
    return groups


def main() -> int:
    content_root = Path("content")
    out_root = Path("publish_site")
    if out_root.exists():
        for path in sorted(out_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    out_root.mkdir(parents=True, exist_ok=True)
    assets_dir = out_root / "assets" / "slides"
    assets_dir.mkdir(parents=True, exist_ok=True)

    groups = collect_groups(content_root, out_root)
    (out_root / "index.html").write_text(build_index(groups), encoding="utf-8")
    (out_root / ".nojekyll").write_text("", encoding="utf-8")
    for group in groups:
        target_dir = out_root / str(group["slug"])
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(build_group_page(group, groups), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
