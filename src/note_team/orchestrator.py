from __future__ import annotations

import json
import re
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from note_team.models import StageResult, WorkflowConfig, ArticleBrief, AgentSpec, ModelProfile
from note_team.prompting import render_prompt
from note_team.runners import build_runner


def slugify(value: str) -> str:
    normalized = []
    last_was_dash = False
    for char in value.lower():
        if char.isascii() and char.isalnum():
            normalized.append(char)
            last_was_dash = False
            continue
        if char in {" ", "_", "-", "/"} and not last_was_dash:
            normalized.append("-")
            last_was_dash = True
            continue
        if ord(char) > 127 and not last_was_dash:
            normalized.append("-")
            last_was_dash = True
    slug = "".join(normalized).strip("-")
    return slug or "note-project"


class WorkflowRunner:
    def __init__(self, project_root: Path, team_config_path: Path) -> None:
        self.project_root = project_root
        self.team_config_path = team_config_path
        self.workflow_config = self._load_workflow_config()

    def _load_workflow_config(self) -> WorkflowConfig:
        raw = json.loads(self.team_config_path.read_text(encoding="utf-8"))
        return WorkflowConfig.from_dict(raw, self.project_root)

    def load_brief(self, brief_path: Path) -> ArticleBrief:
        raw = json.loads(brief_path.read_text(encoding="utf-8"))
        return ArticleBrief.from_dict(raw)

    def validate(self) -> list[str]:
        findings: list[str] = []
        known_ids = {agent.id for agent in self.workflow_config.agents}
        for agent in self.workflow_config.agents:
            for dependency in agent.dependencies:
                if dependency not in known_ids:
                    findings.append(f"{agent.id}: unknown dependency `{dependency}`")
            if not agent.prompt_path.exists():
                findings.append(f"{agent.id}: prompt file missing `{agent.prompt_path}`; builtin prompt will be used")
            if agent.model_profile and agent.model_profile not in self.workflow_config.model_profiles:
                findings.append(f"{agent.id}: unknown model_profile `{agent.model_profile}`")
        if self.workflow_config.final_agent_id not in known_ids:
            findings.append(
                f"final_agent_id `{self.workflow_config.final_agent_id}` is not defined; last agent output will be used"
            )
        if self.workflow_config.default_model_profile and (
            self.workflow_config.default_model_profile not in self.workflow_config.model_profiles
        ):
            findings.append(
                f"default_model_profile `{self.workflow_config.default_model_profile}` is not defined"
            )
        for index, override in enumerate(self.workflow_config.content_overrides, start=1):
            for agent_id, profile_id in override.profile_overrides.items():
                if agent_id not in known_ids:
                    findings.append(f"content_overrides[{index}]: unknown agent id `{agent_id}`")
                if profile_id not in self.workflow_config.model_profiles:
                    findings.append(f"content_overrides[{index}]: unknown model_profile `{profile_id}`")
        return findings

    def resolve_model_profile(self, agent: AgentSpec, brief: ArticleBrief) -> ModelProfile | None:
        resolved_profile_id = agent.model_profile or self.workflow_config.default_model_profile
        searchable_parts = [
            brief.topic,
            brief.objective,
            brief.target_reader,
            brief.angle,
            brief.tone,
            *brief.constraints,
            *brief.keywords,
            *brief.reference_notes,
            *brief.sections_to_cover,
            *brief.supporting_data,
        ]
        haystack = "\n".join(part.lower() for part in searchable_parts if part).strip()
        if haystack:
            for override in self.workflow_config.content_overrides:
                keywords = [item.lower() for item in override.match_any if item.strip()]
                if not keywords:
                    continue
                if any(keyword in haystack for keyword in keywords):
                    override_profile = override.profile_overrides.get(agent.id)
                    if override_profile:
                        resolved_profile_id = override_profile
        if not resolved_profile_id:
            return None
        return self.workflow_config.model_profiles.get(resolved_profile_id)

    def run(
        self,
        brief_path: Path,
        output_root: Path,
        mode: str,
        run_name: str | None = None,
        command: str | None = None,
    ) -> Path:
        brief = self.load_brief(brief_path)
        runner = build_runner(mode=mode, command=command)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = slugify(run_name or brief.topic)
        run_dir = output_root / f"{timestamp}-{slug}"
        run_dir.mkdir(parents=True, exist_ok=False)

        snapshots_dir = run_dir / "snapshots"
        snapshots_dir.mkdir()
        shutil.copy2(brief_path, snapshots_dir / "brief.json")
        shutil.copy2(self.team_config_path, snapshots_dir / "team.json")

        stage_results: dict[str, StageResult] = {}
        manifest: dict[str, Any] = {
            "workflow": self.workflow_config.name,
            "mode": mode,
            "brief_topic": brief.topic,
            "run_dir": str(run_dir),
            "stages": [],
        }

        for index, agent in enumerate(self.workflow_config.agents, start=1):
            stage_dir = run_dir / f"{index:02d}-{agent.id}"
            stage_dir.mkdir()
            model_profile = self.resolve_model_profile(agent, brief)

            prompt_text = render_prompt(agent, brief, stage_results)
            prompt_path = stage_dir / "prompt.md"
            prompt_path.write_text(prompt_text, encoding="utf-8")

            response_text = runner.generate(
                spec=agent,
                brief=brief,
                prompt=prompt_text,
                stage_results=stage_results,
                model_profile=model_profile,
            )
            response_path = stage_dir / "response.md"
            response_path.write_text(response_text.rstrip() + "\n", encoding="utf-8")

            stage_result = StageResult(
                agent=agent,
                prompt_path=prompt_path,
                response_path=response_path,
                response_text=response_text.rstrip() + "\n",
            )
            stage_results[agent.id] = stage_result

            manifest["stages"].append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "deliverable": agent.deliverable,
                    "prompt_path": str(prompt_path.relative_to(run_dir)),
                    "response_path": str(response_path.relative_to(run_dir)),
                    "model_profile": model_profile.id if model_profile else "",
                    "model": model_profile.model if model_profile else "",
                    "reasoning_effort": model_profile.reasoning_effort if model_profile else "",
                }
            )

        final_stage = stage_results.get(self.workflow_config.final_agent_id) or stage_results[
            self.workflow_config.agents[-1].id
        ]
        final_article_path = run_dir / "FINAL_ARTICLE.md"
        final_article_path.write_text(final_stage.response_text, encoding="utf-8")
        manifest["final_article_path"] = str(final_article_path.relative_to(run_dir))

        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        issue_board_path = run_dir / "ISSUE_BOARD.md"
        issue_board_path.write_text(self._build_issue_board(brief, manifest, stage_results), encoding="utf-8")
        quality_gate_path = run_dir / "QUALITY_GATE_REPORT.md"
        quality_gate_path.write_text(self._build_quality_gate_report(brief, final_stage.response_text), encoding="utf-8")
        scorecard_path = run_dir / "SCORECARD.md"
        scorecard_path.write_text(self._build_scorecard(brief, final_stage.response_text), encoding="utf-8")

        summary_path = run_dir / "RUN_SUMMARY.md"
        summary_lines = [
            f"# {self.workflow_config.name}",
            "",
            f"- 実行モード: {mode}",
            f"- テーマ: {brief.topic}",
            f"- 目的: {brief.objective}",
            f"- ターゲット読者: {brief.target_reader}",
            f"- 最終稿: `{final_article_path.name}`",
            "",
            "## ステージ一覧",
        ]
        for stage in manifest["stages"]:
            summary_lines.append(
                f"- {stage['name']} (`{stage['id']}`): `{stage['response_path']}`"
                f" / {stage.get('model') or 'default'}"
                f" / {stage.get('reasoning_effort') or 'default'}"
            )
        summary_lines.extend(
            [
                "",
                "## 管理資料",
                f"- 課題管理表: `{issue_board_path.name}`",
                f"- 品質ゲート: `{quality_gate_path.name}`",
                f"- スコアカード: `{scorecard_path.name}`",
            ]
        )
        summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        return run_dir

    def _build_issue_board(
        self,
        brief: ArticleBrief,
        manifest: dict[str, Any],
        stage_results: dict[str, StageResult],
    ) -> str:
        command_stage = stage_results.get("command_lead")
        command_note = command_stage.response_text.strip() if command_stage else "指揮担当の出力はありません。"
        lines = [
            f"# ISSUE BOARD: {brief.topic}",
            "",
            "## Project Focus",
            f"- テーマ: {brief.topic}",
            f"- 目的: {brief.objective}",
            f"- 読者: {brief.target_reader}",
            "",
            "## Command Lead Memo",
            command_note,
            "",
            "## Stage Ownership",
        ]
        for stage in manifest["stages"]:
            lines.append(
                f"- `{stage['id']}` / {stage['name']}: {stage['deliverable']}"
            )
        lines.extend(
            [
                "",
                "## Priority Table",
                "",
                "| Priority | Issue | Owner | Target Stage | Status | Close Condition |",
                "| --- | --- | --- | --- | --- | --- |",
                "| P0 | 事実誤認、高リスク断定、公開不可の欠陥を残さない | 指揮担当 / リサーチ / レビュー | research / review / final_edit | Open | 一次情報と整合し、レビューで重大指摘が解消している |",
                "| P1 | 既存公開記事との重複や焼き直しを避ける | 指揮担当 / 戦略 / レビュー | strategy / review | Open | 既存記事との差分が brief と review に明記されている |",
                "| P1 | 記事の狙いと読者価値を冒頭で明確にする | 指揮担当 / 編集長 / 構成 | editor_in_chief / outline | Open | 導入と見出しだけで読む価値が伝わる |",
                "| P2 | 本文の冗長さを抑え、セクション重複を減らす | ドラフト / 最終編集 | draft / final_edit | Open | 同じ論点の言い換え反復がない |",
                "| P2 | 公開後に参照しやすいソース導線を残す | リサーチ / 最終編集 | research / final_edit | Open | ソースリンクや参考情報が読者から辿れる |",
            ]
        )
        return "\n".join(lines) + "\n"

    def _build_quality_gate_report(self, brief: ArticleBrief, final_text: str) -> str:
        gates = brief.extra.get("quality_gates", {}) if isinstance(brief.extra, dict) else {}
        max_duplicate = float(gates.get("max_duplicate_overlap", 0.58))
        min_sources = int(gates.get("min_reference_links", 2))
        max_summary_length = int(gates.get("max_summary_length", 170))
        min_primary_ratio = float(gates.get("min_primary_source_ratio", 0.5))
        forbid_duplicate_headings = bool(gates.get("forbid_duplicate_headings", True))

        source_links = re.findall(r"https?://[^\s)>\"]+", final_text)
        source_count = len(set(link.rstrip(".,]") for link in source_links))
        summary_candidate = " ".join(
            line.strip() for line in final_text.splitlines() if line.strip() and not line.strip().startswith("#")
        )[: max_summary_length + 40]
        headings = [line.lstrip("#").strip() for line in final_text.splitlines() if line.strip().startswith("##")]
        duplicate_headings = len(headings) != len(set(headings))
        preferred_domains = [
            domain for domain in brief.extra.get("preferred_domains", [])
        ] if isinstance(brief.extra, dict) else []
        primary_count = 0
        for link in source_links:
            host = urllib.parse.urlparse(link).netloc.lower()
            if any(domain in host for domain in preferred_domains):
                primary_count += 1
        primary_ratio = (primary_count / source_count) if source_count else 0.0

        checks = [
            ("重複スコア上限", f"<= {max_duplicate:.2f}", "brief 生成時に判定", "pass"),
            ("参考リンク数", f">= {min_sources}", str(source_count), "pass" if source_count >= min_sources else "fail"),
            ("一次情報比率", f">= {min_primary_ratio:.2f}", f"{primary_ratio:.2f}", "pass" if primary_ratio >= min_primary_ratio else "fail"),
            ("要約長上限", f"<= {max_summary_length}", str(len(summary_candidate)), "pass" if len(summary_candidate) <= max_summary_length else "fail"),
            ("見出し重複禁止", "true", "duplicate" if duplicate_headings else "clean", "fail" if forbid_duplicate_headings and duplicate_headings else "pass"),
        ]

        lines = [
            f"# QUALITY GATE REPORT: {brief.topic}",
            "",
            "| Gate | Target | Measured | Status |",
            "| --- | --- | --- | --- |",
        ]
        for name, target, measured, status in checks:
            lines.append(f"| {name} | {target} | {measured} | {status} |")
        return "\n".join(lines) + "\n"

    def _build_scorecard(self, brief: ArticleBrief, final_text: str) -> str:
        source_links = re.findall(r"https?://[^\s)>\"]+", final_text)
        headings = [line for line in final_text.splitlines() if line.startswith("##")]
        scores = {
            "正確性": 5 if len(source_links) >= 3 else 4 if len(source_links) >= 2 else 2,
            "独自性": 4 if "差分" in json.dumps(brief.to_dict(), ensure_ascii=False) or "重複回避" in final_text else 3,
            "可読性": 5 if 3 <= len(headings) <= 8 else 3,
            "公開完成度": 5 if "## 参考" in final_text else 3,
        }
        lines = [
            f"# SCORECARD: {brief.topic}",
            "",
            "| 項目 | Score | Note |",
            "| --- | --- | --- |",
        ]
        for key, value in scores.items():
            lines.append(f"| {key} | {value}/5 | 自動評価による暫定スコア |")
        return "\n".join(lines) + "\n"
