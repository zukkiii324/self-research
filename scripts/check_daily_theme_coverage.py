#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass
class TopicCoverage:
    topic_id: str
    label: str
    output_dir: str
    slug: str
    has_today_article: bool
    today_article: str
    latest_article: str
    latest_date: str


def load_topics(catalog_path: Path) -> list[dict[str, object]]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [item for item in payload.get("topics", []) if item.get("publish", True)]


def collect_topic_coverage(content_root: Path, topic: dict[str, object], target_date: str) -> TopicCoverage:
    output_dir = str(topic["output_dir"])
    slug = str(topic["id"])
    topic_dir = content_root / output_dir
    articles = sorted(
        [
            path for path in topic_dir.glob("*.md")
            if not path.name.lower().startswith("readme")
        ],
        reverse=True,
    ) if topic_dir.exists() else []
    today_article = ""
    latest_article = articles[0].name if articles else ""
    latest_date = latest_article[:10] if latest_article[:10].count("-") == 2 else ""
    for article in articles:
        if article.name.startswith(f"{target_date}-"):
            today_article = article.name
            break
    return TopicCoverage(
        topic_id=slug,
        label=str(topic["label"]),
        output_dir=output_dir,
        slug=slug,
        has_today_article=bool(today_article),
        today_article=today_article,
        latest_article=latest_article,
        latest_date=latest_date,
    )


def build_report(topics: list[TopicCoverage], target_date: str) -> dict[str, object]:
    missing = [topic for topic in topics if not topic.has_today_article]
    return {
        "date": target_date,
        "generated_at": datetime.now().isoformat(),
        "published_topic_count": len(topics),
        "completed_topic_count": len(topics) - len(missing),
        "missing_topic_count": len(missing),
        "topics": [topic.__dict__ for topic in topics],
        "missing_topic_ids": [topic.topic_id for topic in missing],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        f"# Daily Theme Coverage {report['date']}",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- published_topics: `{report['published_topic_count']}`",
        f"- completed_today: `{report['completed_topic_count']}`",
        f"- missing_today: `{report['missing_topic_count']}`",
        "",
        "## Topics",
        "",
        "| Theme | Status | Today's Article | Latest Article |",
        "| --- | --- | --- | --- |",
    ]
    for topic in report["topics"]:
        status = "done" if topic["has_today_article"] else "missing"
        today_article = topic["today_article"] or "-"
        latest_article = topic["latest_article"] or "-"
        lines.append(f"| {topic['label']} | {status} | `{today_article}` | `{latest_article}` |")
    if report["missing_topic_ids"]:
        lines.extend([
            "",
            "## Missing Topics",
            "",
            *[f"- `{topic_id}`" for topic_id in report["missing_topic_ids"]],
        ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="公開対象テーマの今日の記事有無を点検する")
    parser.add_argument("--catalog", default="config/topic_catalog.json")
    parser.add_argument("--content-root", default="content")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output-dir", default="automation/daily_coverage")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    topics = load_topics(Path(args.catalog))
    coverage = [
        collect_topic_coverage(Path(args.content_root), topic, args.date)
        for topic in topics
    ]
    report = build_report(coverage, args.date)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.date
    (output_dir / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{stem}.md").write_text(render_markdown(report), encoding="utf-8")

    return 1 if args.fail_on_missing and report["missing_topic_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
