#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
import re


def collect_articles(content_root: Path) -> list[dict[str, str]]:
    articles: list[dict[str, str]] = []
    for md in sorted(content_root.rglob("*.md")):
        rel = md.relative_to(content_root)
        if rel.name.lower().startswith("readme"):
            continue
        with md.open(encoding="utf-8") as fh:
            title = ""
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("#"):
                    title = stripped.lstrip("#").strip()
                    break
        if not title:
            title = rel.stem.replace("-", " ").capitalize()
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", rel.stem)
        articles.append(
            {
                "source": str(md),
                "relative": str(rel),
                "title": title,
                "date": date_match.group(1) if date_match else "",
                "group": rel.parts[0] if len(rel.parts) > 1 else "general",
            }
        )
    return articles


def build_index(articles: list[dict[str, str]], docs_root: Path) -> None:
    lines = [
        "# Note Multi-Agent Content Library",
        "",
        "自動生成された記事一覧です。各タイトルをクリックすると、該当の Markdown が表示されます。",
        "",
    ]
    articles_by_group: dict[str, list[dict[str, str]]] = {}
    for article in articles:
        articles_by_group.setdefault(article["group"], []).append(article)

    for group in sorted(articles_by_group):
        lines.append(f"## {group}")
        for article in articles_by_group[group]:
            rel_path = article["relative"]
            display_date = f" ({article['date']})" if article["date"] else ""
            lines.append(f"- [{article['title']}](./{rel_path}){display_date}")
        lines.append("")

    index_path = docs_root / "index.md"
    index_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def sync_markdown(articles: list[dict[str, str]], content_root: Path, docs_root: Path) -> None:
    if docs_root.exists():
        shutil.rmtree(docs_root)
    for article in articles:
        src = Path(article["source"])
        dest = docs_root / article["relative"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static MkDocs site from generated content")
    parser.add_argument(
        "--content-root",
        type=Path,
        default=Path("content"),
        help="source directory where generated markdown lives",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("static_blog_site/docs"),
        help="target mkdocs docs directory",
    )
    args = parser.parse_args()
    args.docs_root.mkdir(parents=True, exist_ok=True)

    articles = collect_articles(args.content_root)
    if not articles:
        raise SystemExit("no markdown articles found")

    sync_markdown(articles, args.content_root, args.docs_root)
    build_index(articles, args.docs_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
