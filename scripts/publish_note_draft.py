#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


def load_next_draft(queue_root: Path) -> tuple[Path, dict[str, object]] | None:
    queue_files = sorted(queue_root.glob("*.json"))
    for file in queue_files:
        record = json.loads(file.read_text(encoding="utf-8"))
        if record.get("status") == "queued":
            return file, record
    return None


def write_record(file: Path, record: dict[str, object]) -> None:
    file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fill_title(page, title: str) -> None:
    selector = "textarea[placeholder*='タイトル']"
    if page.locator(selector).count():
        page.locator(selector).fill(title)
        return
    page.evaluate("title => document.querySelector('textarea').value = title", title)


def fill_body(page, body: str) -> None:
    editor = page.locator("div.ProseMirror").first()
    editor.click()
    page.keyboard.type(body)


def fill_tags(page, tags: list[str]) -> None:
    if not tags:
        return
    tag_input = page.locator("input[placeholder*='タグ']")
    if not tag_input.count():
        return
    tag_input.fill("")
    for tag in tags:
        tag_input.fill(tag)
        tag_input.press("Enter")


def login(page, email: str, password: str) -> None:
    page.goto("https://note.com/login", wait_until="networkidle")
    page.fill("input[type='email']", email)
    page.fill("input[type='password']", password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_timeout(2000)


def save_draft(page) -> None:
    page.get_by_role("button", name="下書き保存").click()
    page.wait_for_timeout(2000)


def main() -> int:
    parser = argparse.ArgumentParser(description=" noteの記事をnote.comに下書き保存する")
    parser.add_argument(
        "--queue-root",
        type=Path,
        default=Path("queues/drafts"),
        help="下書きキューのディレクトリ",
    )
    parser.add_argument("--headless", action="store_true", help="Playwrightをheadlessで起動する")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="UI操作はせずに対象ファイルだけ確認する",
    )

    args = parser.parse_args()
    email = os.environ.get("NOTE_EMAIL")
    password = os.environ.get("NOTE_PASSWORD")
    if not email or not password:
        raise SystemExit("NOTE_EMAIL / NOTE_PASSWORD を環境変数で指定してください")

    draft = load_next_draft(args.queue_root)
    if not draft:
        raise SystemExit("queued status のドラフトが見つかりません")
    file_path, record = draft
    print(f"投稿対象: {file_path}")

    if args.dry_run:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        page = browser.new_page()
        login(page, email, password)
        page.goto("https://note.com/create", wait_until="networkidle")
        fill_title(page, record["title"])
        fill_body(page, record["body"])
        fill_tags(page, record.get("tags", []))
        save_draft(page)
        record["status"] = "draft_created"
        record["note_url"] = page.url
        record["last_saved_at"] = datetime.now().isoformat(timespec="seconds")
        write_record(file_path, record)
        browser.close()

    print(f"下書き保存完了：{record['note_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
