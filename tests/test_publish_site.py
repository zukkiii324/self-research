from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "build_publish_site.py"
SPEC = importlib.util.spec_from_file_location("build_publish_site", MODULE_PATH)
assert SPEC and SPEC.loader
publish_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publish_site
SPEC.loader.exec_module(publish_site)


class PublishSiteTest(unittest.TestCase):
    def test_reference_section_uses_clickable_labels(self) -> None:
        markdown_text = "\n".join(
            [
                "# 見出し",
                "",
                "本文です。",
                "",
                "## 参考",
                "",
                "- デジタル庁「防災」: https://www.digital.go.jp/policies/disaster_prevention",
            ]
        )
        normalized = publish_site.normalize_reference_section(
            markdown_text,
            ["https://www.digital.go.jp/policies/disaster_prevention"],
        )
        self.assertIn("[デジタル庁「防災」](https://www.digital.go.jp/policies/disaster_prevention)", normalized)
        self.assertNotIn("Source Links", normalized)

    def test_generated_page_contains_mobile_safeguards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            content_root = base / "content"
            out_root = base / "publish_site"
            topic_dir = content_root / "2026-04-baby-week1"
            topic_dir.mkdir(parents=True, exist_ok=True)
            (topic_dir / "2026-04-01-sample.md").write_text(
                "# サンプル記事\n\n本文です。\n\n## 参考\n\n- 公式サイト: https://example.com/reference\n",
                encoding="utf-8",
            )

            groups = publish_site.collect_groups(content_root, out_root)
            html = publish_site.build_group_page(groups[0], groups)

            self.assertIn("@media (max-width: 420px)", html)
            self.assertIn("overflow-wrap: anywhere;", html)
            self.assertIn('<a href="https://example.com/reference">公式サイト</a>', html)
            self.assertIn('class="infographic-panel"', html)
            self.assertIn('class="info-stats"', html)


if __name__ == "__main__":
    unittest.main()
