from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "check_daily_theme_coverage.py"
SPEC = importlib.util.spec_from_file_location("check_daily_theme_coverage", MODULE_PATH)
assert SPEC and SPEC.loader
coverage_script = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = coverage_script
SPEC.loader.exec_module(coverage_script)


class DailyThemeCoverageTest(unittest.TestCase):
    def test_report_marks_missing_topics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            catalog_path = base / "topic_catalog.json"
            content_root = base / "content"
            (content_root / "topic-a").mkdir(parents=True, exist_ok=True)
            (content_root / "topic-b").mkdir(parents=True, exist_ok=True)
            (content_root / "topic-a" / "2026-04-08-a.md").write_text("# A\n", encoding="utf-8")
            (content_root / "topic-b" / "2026-04-07-b.md").write_text("# B\n", encoding="utf-8")
            catalog_path.write_text(
                json.dumps(
                    {
                        "topics": [
                            {"id": "a", "label": "A", "output_dir": "topic-a", "publish": True},
                            {"id": "b", "label": "B", "output_dir": "topic-b", "publish": True},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            topics = coverage_script.load_topics(catalog_path)
            coverage = [
                coverage_script.collect_topic_coverage(content_root, topic, "2026-04-08")
                for topic in topics
            ]
            report = coverage_script.build_report(coverage, "2026-04-08")
            self.assertEqual(report["completed_topic_count"], 1)
            self.assertEqual(report["missing_topic_count"], 1)
            self.assertEqual(report["missing_topic_ids"], ["b"])


if __name__ == "__main__":
    unittest.main()
