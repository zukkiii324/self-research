#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


def slugify(value: str) -> str:
    chars: list[str] = []
    last_dash = False
    for char in value.lower():
        if char.isascii() and char.isalnum():
            chars.append(char)
            last_dash = False
            continue
        if char in {" ", "_", "-", "/"} and not last_dash:
            chars.append("-")
            last_dash = True
            continue
        if ord(char) > 127 and not last_dash:
            chars.append("-")
            last_dash = True
    return "".join(chars).strip("-") or "note-article"


def build_metadata(
    article_path: Path,
    tags: list[str],
    scheduled_at: str | None,
    publish_mode: str,
) -> dict[str, object]:
    text = article_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    title = ""
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break
    if not title:
        title = article_path.stem.replace("-", " ").title()
    body = text.strip()
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "title": title,
        "body": body,
        "tags": tags,
        "status": "queued",
        "publish_mode": publish_mode,
        "scheduled_at": scheduled_at,
        "created_at": now,
        "source": str(article_path),
        "content_hash": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage a Note article as a draft record")
    parser.add_argument("article", type=Path, help="path to the markdown article")
    parser.add_argument(
        "--tags", nargs="+", default=["note", "AI", "DX"], help="tags to attach when posting"
    )
    parser.add_argument(
        "--scheduled-at",
        help="ISO datetime when the article should be published (note premium required)",
    )
    parser.add_argument(
        "--publish-mode",
        choices=["draft", "scheduled"],
        default="scheduled",
        help="how the staged entry should be published",
    )
    parser.add_argument(
        "--queue-root",
        type=Path,
        default=Path("queues/drafts"),
        help="directory to place draft metadata",
    )

    args = parser.parse_args()
    args.queue_root.mkdir(parents=True, exist_ok=True)

    metadata = build_metadata(
        article_path=args.article,
        tags=args.tags,
        scheduled_at=args.scheduled_at,
        publish_mode=args.publish_mode,
    )
    base_name = f"{datetime.now():%Y%m%d-%H%M%S}-{slugify(metadata['title'])}.json"

    target_path = args.queue_root / base_name
    target_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
