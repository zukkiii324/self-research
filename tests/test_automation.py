from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from note_team.automation import (
    FeedEntry,
    PublishedArticle,
    TopicSpec,
    build_brief_payload,
    candidate_overlap_score,
    choose_article_candidate,
    load_research_cache,
    update_research_cache,
)


class AutomationTest(unittest.TestCase):
    def test_candidate_overlap_uses_summary(self) -> None:
        entry = FeedEntry(
            title="Claudeの新機能",
            link="https://example.com/new",
            summary="Claudeのワークフローと監視方法を整理した発表",
            published_at=None,
            source_domain="example.com",
        )
        article = PublishedArticle(
            path=Path("content/sample.md"),
            title="Claude監視方法",
            summary="ワークフローと監視方法を解説",
            tokens={"claudeのワークフローと監視方法を整理した発表"},
            headings=("監視方法",),
            topic_dir="2026-04-claude-week1",
            char_ngrams={"cla", "lau", "aud"},
        )
        self.assertGreater(candidate_overlap_score(entry, article), 0.0)

    def test_build_brief_payload_includes_style_and_mode(self) -> None:
        topic = TopicSpec(
            id="claude",
            label="Claude活用",
            description="",
            output_dir="2026-04-claude-week1",
            automation_enabled=True,
            target_reader="開発者",
            tone="構造的",
            style_guide={"cta_style": "1工程だけ置き換えてください。"},
            brief_template={"sections_to_cover": ["差分", "影響"]},
            quality_gates={"min_reference_links": 2},
        )
        entry = FeedEntry(
            title="Claude新発表",
            link="https://example.com/claude",
            summary="新しい発表の要約",
            published_at=None,
            source_domain="example.com",
        )
        related = [
            PublishedArticle(
                path=Path("content/old.md"),
                title="既存記事",
                summary="過去の整理",
                tokens={"既存", "整理"},
                headings=("既存記事",),
                topic_dir="2026-04-claude-week1",
                char_ngrams={"既存", "整理"},
            )
        ]
        payload = build_brief_payload(topic, entry, related, {"entries": []}, "update", related[0])
        self.assertEqual(payload["extra"]["article_mode"], "update")
        self.assertEqual(payload["sections_to_cover"], ["差分", "影響"])
        self.assertEqual(payload["call_to_action"], "1工程だけ置き換えてください。")
        self.assertEqual(payload["extra"]["quality_gates"]["min_reference_links"], 2)

    def test_research_cache_roundtrip(self) -> None:
        topic = TopicSpec(id="disaster_dx", label="防災DX", description="", output_dir="disaster-dx-watch")
        entry = FeedEntry(
            title="防災DXの新発表",
            link="https://example.com/disaster",
            summary="要約",
            published_at=None,
            source_domain="example.com",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            update_research_cache(project_root, topic, entry, Path("content/disaster.md"))
            cache = load_research_cache(project_root, topic)
            self.assertEqual(cache["topic_id"], "disaster_dx")
            self.assertEqual(cache["entries"][0]["title"], "防災DXの新発表")

    def test_choose_article_candidate_prefers_same_topic_update(self) -> None:
        topic = TopicSpec(
            id="claude",
            label="Claude活用",
            description="",
            output_dir="2026-04-claude-week1",
            automation_enabled=True,
            preferred_domains=["example.com"],
        )
        entry = FeedEntry(
            title="Claude monitor refresh",
            link="https://example.com/new-guide",
            summary="monitor review changes and design updates",
            published_at=None,
            source_domain="example.com",
        )
        article = PublishedArticle(
            path=Path("content/2026-04-claude-week1/2026-04-06-claude-monitoring.md"),
            title="Claude monitor guide",
            summary="monitor design review basics",
            tokens={"claude", "monitor", "guide", "design", "review", "basics"},
            headings=("monitor design", "review basics"),
            topic_dir="2026-04-claude-week1",
            char_ngrams={"cla", "mon", "rev", "gui", "des", "bas"},
        )

        with patch("note_team.automation.collect_recent_entries", return_value=[entry]):
            selected_topic, _, _, target_article, article_mode = choose_article_candidate(
                topics=[topic],
                published_articles=[article],
                max_age_hours=8,
            )

        self.assertEqual(selected_topic.id, "claude")
        self.assertEqual(article_mode, "update")
        self.assertEqual(target_article.path, article.path)


if __name__ == "__main__":
    unittest.main()
