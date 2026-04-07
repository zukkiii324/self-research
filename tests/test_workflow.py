from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from note_team.orchestrator import WorkflowRunner


class WorkflowRunnerTest(unittest.TestCase):
    def test_mock_run_creates_final_article(self) -> None:
        brief_data = {
            "topic": "社内ナレッジをNote記事に変換する運用",
            "objective": "記事の企画から公開までの流れを標準化する",
            "target_reader": "情報発信を始めたいチームリーダー",
            "angle": "現場で運用できるプロセス設計",
            "tone": "実務的で親しみやすい",
            "call_to_action": "まずは一つの社内メモを記事候補として洗い出してください。",
            "constraints": ["未確認の数値は断定しない", "社外秘情報は書かない"],
            "keywords": ["ナレッジ共有", "Note運用", "編集体制"],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            brief_path = temp_path / "brief.json"
            brief_path.write_text(json.dumps(brief_data, ensure_ascii=False, indent=2), encoding="utf-8")

            runner = WorkflowRunner(
                project_root=PROJECT_ROOT,
                team_config_path=PROJECT_ROOT / "config/note_editorial_team.json",
            )
            run_dir = runner.run(
                brief_path=brief_path,
                output_root=temp_path / "runs",
                mode="mock",
            )

            self.assertTrue((run_dir / "FINAL_ARTICLE.md").exists())
            final_text = (run_dir / "FINAL_ARTICLE.md").read_text(encoding="utf-8")
            self.assertIn("判断軸", final_text)
            self.assertTrue((run_dir / "RUN_SUMMARY.md").exists())

    def test_sample_brief_format_is_supported(self) -> None:
        runner = WorkflowRunner(
            project_root=PROJECT_ROOT,
            team_config_path=PROJECT_ROOT / "config/note_editorial_team.json",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            run_dir = runner.run(
                brief_path=PROJECT_ROOT / "examples/brief.sample.json",
                output_root=temp_path / "runs",
                mode="mock",
                run_name="sample-brief-smoke-test",
            )

            self.assertTrue((run_dir / "FINAL_ARTICLE.md").exists())
            self.assertTrue((run_dir / "01-editor_in_chief" / "prompt.md").exists())
            self.assertTrue((run_dir / "07-final_edit" / "response.md").exists())


if __name__ == "__main__":
    unittest.main()
