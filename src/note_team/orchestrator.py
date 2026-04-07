from __future__ import annotations

import json
import shutil
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
        summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        return run_dir
