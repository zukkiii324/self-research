from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _ensure_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " / ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _ensure_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("name") or "").strip()
                note = str(item.get("note") or item.get("summary") or item.get("value") or "").strip()
                text = ": ".join(part for part in [label, note] if part)
            else:
                text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value).strip()]


@dataclass
class ArticleBrief:
    topic: str
    objective: str
    target_reader: str
    angle: str = ""
    tone: str = ""
    call_to_action: str = ""
    constraints: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    reference_notes: list[str] = field(default_factory=list)
    sections_to_cover: list[str] = field(default_factory=list)
    supporting_data: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ArticleBrief":
        source = raw.get("brief") if isinstance(raw.get("brief"), dict) else raw

        topic = _ensure_text(source.get("topic") or source.get("theme") or source.get("テーマ"))
        objective = _ensure_text(source.get("objective") or source.get("goal"))
        target_reader = _ensure_text(source.get("target_reader") or source.get("audience") or source.get("reader"))

        missing: list[str] = []
        if not topic:
            missing.append("topic")
        if not objective:
            missing.append("objective")
        if not target_reader:
            missing.append("target_reader")
        if missing:
            raise ValueError("brief is missing required fields: " + ", ".join(missing))

        known_keys = {
            "topic",
            "theme",
            "テーマ",
            "objective",
            "goal",
            "target_reader",
            "audience",
            "reader",
            "angle",
            "tone",
            "length_range",
            "call_to_action",
            "cta",
            "constraints",
            "keywords",
            "reference_notes",
            "notes",
            "sources",
            "references",
            "sections_to_cover",
            "must_cover",
            "supporting_data",
            "deliverables",
        }
        extra = {key: value for key, value in raw.items() if key != "brief"}
        extra.update({key: value for key, value in source.items() if key not in known_keys})

        return cls(
            topic=topic,
            objective=objective,
            target_reader=target_reader,
            angle=_ensure_text(source.get("angle")),
            tone=_ensure_text(source.get("tone")),
            call_to_action=_ensure_text(source.get("call_to_action") or source.get("cta")),
            constraints=_ensure_list(source.get("constraints")),
            keywords=_ensure_list(source.get("keywords")),
            reference_notes=_ensure_list(
                source.get("reference_notes") or source.get("notes") or source.get("sources") or source.get("references")
            ),
            sections_to_cover=_ensure_list(source.get("sections_to_cover") or source.get("must_cover")),
            supporting_data=_ensure_list(source.get("supporting_data") or source.get("deliverables")),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "topic": self.topic,
            "objective": self.objective,
            "target_reader": self.target_reader,
            "angle": self.angle,
            "tone": self.tone,
            "call_to_action": self.call_to_action,
            "constraints": self.constraints,
            "keywords": self.keywords,
            "reference_notes": self.reference_notes,
            "sections_to_cover": self.sections_to_cover,
            "supporting_data": self.supporting_data,
        }
        data.update(self.extra)
        return data


@dataclass
class AgentSpec:
    id: str
    name: str
    department: str
    mission: str
    prompt_path: Path
    deliverable: str
    dependencies: list[str] = field(default_factory=list)
    model_profile: str = ""


@dataclass
class ModelProfile:
    id: str
    model: str
    reasoning_effort: str = ""
    notes: str = ""


@dataclass
class ContentOverride:
    match_any: list[str] = field(default_factory=list)
    profile_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    name: str
    description: str
    agents: list[AgentSpec]
    final_agent_id: str
    model_profiles: dict[str, ModelProfile] = field(default_factory=dict)
    default_model_profile: str = ""
    content_overrides: list[ContentOverride] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], project_root: Path) -> "WorkflowConfig":
        agents: list[AgentSpec] = []
        for item in raw.get("agents", []):
            agents.append(
                AgentSpec(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    department=str(item.get("department") or ""),
                    mission=str(item["mission"]),
                    prompt_path=project_root / str(item["prompt_path"]),
                    deliverable=str(item["deliverable"]),
                    dependencies=[str(dep) for dep in item.get("dependencies", [])],
                    model_profile=str(item.get("model_profile") or ""),
                )
            )
        if not agents:
            raise ValueError("workflow config must define at least one agent")

        model_profiles: dict[str, ModelProfile] = {}
        for profile_id, item in (raw.get("model_profiles") or {}).items():
            model_profiles[str(profile_id)] = ModelProfile(
                id=str(profile_id),
                model=str(item.get("model") or "").strip(),
                reasoning_effort=str(item.get("reasoning_effort") or "").strip(),
                notes=str(item.get("notes") or "").strip(),
            )

        content_overrides: list[ContentOverride] = []
        for item in raw.get("content_overrides", []) or []:
            profile_overrides = {
                str(agent_id): str(profile_id)
                for agent_id, profile_id in (item.get("profile_overrides") or {}).items()
                if str(agent_id).strip() and str(profile_id).strip()
            }
            content_overrides.append(
                ContentOverride(
                    match_any=_ensure_list(item.get("match_any") or item.get("keywords")),
                    profile_overrides=profile_overrides,
                )
            )

        final_agent_id = str(raw.get("final_agent_id") or agents[-1].id)
        return cls(
            name=str(raw.get("name") or "Note Editorial Room"),
            description=str(raw.get("description") or ""),
            agents=agents,
            final_agent_id=final_agent_id,
            model_profiles=model_profiles,
            default_model_profile=str(raw.get("default_model_profile") or "").strip(),
            content_overrides=content_overrides,
        )


@dataclass
class StageResult:
    agent: AgentSpec
    prompt_path: Path
    response_path: Path
    response_text: str
