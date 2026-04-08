from __future__ import annotations

import json
import re
from string import Template

from note_team.models import AgentSpec, ArticleBrief, StageResult


BUILTIN_PROMPTS: dict[str, str] = {
    "editor_in_chief": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
Note向けの記事制作案件として、勝ち筋が明確になる企画方針書を作成してください。""",
    "strategy": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
読者像、刺さる課題、タイトル案、導入フックを具体化してください。""",
    "research": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
主張の裏取りが必要な箇所、追加取材の論点、不確実性を整理してください。""",
    "outline": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
読者が最後まで読み進めやすい章立てと各節の要点を作成してください。""",
    "draft": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
構成に沿ってNoteに投稿できる日本語の初稿を書いてください。""",
    "review": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
編集レビューとして、弱い箇所と改善提案を優先度順にまとめてください。""",
    "fact_review": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
事実性、根拠、鮮度、品質ゲートの観点でレビューしてください。""",
    "editorial_review": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
読みやすさ、重複、構成、スタイルガイドの観点でレビューしてください。""",
    "final_edit": """# 役割
$agent_name として動作してください。

# ミッション
$agent_mission

# 案件ブリーフ
```json
$brief_json
```

# 引き継ぎ済みコンテキスト
$upstream_context

# 出力契約
$output_contract

# 指示
レビューを反映し、公開可能な最終稿とタイトル、締めのCTA、想定ハッシュタグを作成してください。""",
}


def build_output_contract(spec: AgentSpec) -> str:
    return (
        f"- 納品物: {spec.deliverable}\n"
        "- 見出し付きMarkdownで出力する\n"
        "- 箇条書きと短い段落を併用し、次工程が引き継ぎやすい粒度にする\n"
        "- 推測と確定情報を混同しない\n"
    )


def build_upstream_context(stage_results: dict[str, StageResult], dependencies: list[str]) -> str:
    if not dependencies:
        return "なし"

    chunks: list[str] = []
    for dependency in dependencies:
        result = stage_results.get(dependency)
        if result is None:
            continue
        chunks.append(f"## {result.agent.name} ({result.agent.id})\n\n{result.response_text}")
    return "\n\n".join(chunks) if chunks else "なし"


def load_prompt_template(spec: AgentSpec) -> str:
    if spec.prompt_path.exists():
        return spec.prompt_path.read_text(encoding="utf-8")
    return BUILTIN_PROMPTS.get(spec.id, BUILTIN_PROMPTS["editor_in_chief"])


def _brace_substitute(template_text: str, mapping: dict[str, str]) -> str:
    pattern = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return mapping.get(key, "")

    return pattern.sub(replace, template_text)


def render_prompt(spec: AgentSpec, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
    template_text = load_prompt_template(spec)
    template = Template(template_text)
    upstream_context = build_upstream_context(stage_results, spec.dependencies)
    mapping: dict[str, str] = {
        "agent_name": spec.name,
        "agent_id": spec.id,
        "agent_mission": spec.mission,
        "brief_json": json.dumps(brief.to_dict(), ensure_ascii=False, indent=2),
        "brief": json.dumps(brief.to_dict(), ensure_ascii=False, indent=2),
        "upstream_context": upstream_context,
        "context": upstream_context,
        "output_contract": build_output_contract(spec),
    }
    for stage_id, result in stage_results.items():
        mapping[stage_id] = result.response_text

    rendered = template.safe_substitute(mapping)
    return _brace_substitute(rendered, mapping)
