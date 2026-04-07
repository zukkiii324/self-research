from __future__ import annotations

import re
import shlex
import subprocess
from abc import ABC, abstractmethod

from note_team.models import AgentSpec, ArticleBrief, StageResult, ModelProfile


def _bullets(items: list[str], fallback: str) -> str:
    lines = items or [fallback]
    return "\n".join(f"- {line}" for line in lines)


def _extract_title_seed(brief: ArticleBrief) -> str:
    if brief.angle and len(brief.angle) <= 24:
        return f"{brief.topic}を{brief.angle}から考える"
    return brief.topic


def _primary_reader(brief: ArticleBrief) -> str:
    readers = [item.strip() for item in brief.target_reader.split("/") if item.strip()]
    return readers[0] if readers else brief.target_reader


class BaseRunner(ABC):
    @abstractmethod
    def generate(
        self,
        spec: AgentSpec,
        brief: ArticleBrief,
        prompt: str,
        stage_results: dict[str, StageResult],
        model_profile: ModelProfile | None = None,
    ) -> str:
        raise NotImplementedError


class ManualRunner(BaseRunner):
    def generate(
        self,
        spec: AgentSpec,
        brief: ArticleBrief,
        prompt: str,
        stage_results: dict[str, StageResult],
        model_profile: ModelProfile | None = None,
    ) -> str:
        return (
            f"# {spec.deliverable}\n\n"
            "このファイルは手動記入モードで生成されました。\n\n"
            "## 次のアクション\n"
            "1. 同じディレクトリにある `prompt.md` を任意のLLMまたは執筆担当者に渡してください。\n"
            "2. 結果をこの `response.md` に反映してください。\n"
            "3. 後続工程は依存する `response.md` を参照します。\n\n"
            "## 記入テンプレート\n"
            "- 要点:\n"
            "- 判断:\n"
            "- 次工程への引き継ぎ:\n"
        )


class CommandRunner(BaseRunner):
    def __init__(self, command: str) -> None:
        self.command = command

    def generate(
        self,
        spec: AgentSpec,
        brief: ArticleBrief,
        prompt: str,
        stage_results: dict[str, StageResult],
        model_profile: ModelProfile | None = None,
    ) -> str:
        command = self.command.format(
            agent_id=spec.id,
            agent_name=spec.name,
            department=spec.department,
            deliverable=spec.deliverable,
            model=model_profile.model if model_profile else "",
            model_profile=model_profile.id if model_profile else "",
            reasoning_effort=model_profile.reasoning_effort if model_profile else "",
        )
        process = subprocess.run(
            shlex.split(command),
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"command runner failed for {spec.id}: "
                f"exit={process.returncode} stderr={process.stderr.strip()}"
            )
        output = process.stdout.strip()
        if not output:
            raise RuntimeError(f"command runner returned empty output for {spec.id}")
        return output


class MockRunner(BaseRunner):
    def generate(
        self,
        spec: AgentSpec,
        brief: ArticleBrief,
        prompt: str,
        stage_results: dict[str, StageResult],
        model_profile: ModelProfile | None = None,
    ) -> str:
        methods = {
            "chief_editor": self._chief_editor,
            "editor_in_chief": self._chief_editor,
            "audience_strategist": self._audience_strategist,
            "strategy": self._audience_strategist,
            "researcher": self._researcher,
            "research": self._researcher,
            "outliner": self._outliner,
            "outline": self._outliner,
            "drafter": self._drafter,
            "draft": self._drafter,
            "reviewer": self._reviewer,
            "review": self._reviewer,
            "final_editor": self._final_editor,
            "final_edit": self._final_editor,
        }
        generator = methods.get(spec.id, self._generic)
        return generator(brief, stage_results)

    def _generic(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        return (
            f"# 作業メモ\n\n"
            f"- テーマ: {brief.topic}\n"
            f"- 目的: {brief.objective}\n"
            f"- 読者: {brief.target_reader}\n"
        )

    def _chief_editor(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        return (
            "# 企画方針書\n\n"
            "## 記事の勝ち筋\n"
            f"- テーマ: {brief.topic}\n"
            f"- 目的: {brief.objective}\n"
            f"- 主要読者: {brief.target_reader}\n"
            f"- 記事の角度: {brief.angle or '読者が実務で再現できる視点を中心に整理する'}\n\n"
            "## 成功条件\n"
            "- 読者が『自分にも試せる』と感じられる具体性がある\n"
            "- Noteらしい個人の実感と再現可能な示唆が両立している\n"
            "- 一読後に次の行動が明確になる\n\n"
            "## 制約と注意点\n"
            f"{_bullets(brief.constraints, '断定しすぎず、事実確認が必要な点は保留表現にする')}\n"
        )

    def _audience_strategist(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        title_seed = _extract_title_seed(brief)
        primary_reader = _primary_reader(brief)
        return (
            "# 読者戦略メモ\n\n"
            "## 想定読者の状態\n"
            f"- 主読者: {brief.target_reader}\n"
            f"- 抱えている課題: {brief.objective} に直結する悩みを抱えている\n"
            "- 欲しいもの: 過度に抽象的ではない、すぐ試せる視点\n\n"
            "## タイトル案\n"
            f"1. {title_seed}ために、最初に整理したい3つの視点\n"
            f"2. {primary_reader}に向けた、{brief.topic}の現実的な始め方\n"
            f"3. {brief.topic}で迷ったときに立ち返れる実践メモ\n\n"
            "## 導入フック\n"
            "- よくあるつまずきの描写から始める\n"
            "- 自分の試行錯誤を短く提示して信頼を作る\n"
            "- 読後に得られる変化を冒頭で明示する\n\n"
            "## 推しキーワード\n"
            f"{_bullets(brief.keywords, brief.topic)}\n"
        )

    def _researcher(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        return (
            "# リサーチ計画\n\n"
            "## 検証したい論点\n"
            f"- {brief.topic}に関する主張のうち、数値や市場動向を含む部分\n"
            "- 個人の体験談として書ける範囲と、一般化が必要な範囲の切り分け\n"
            "- 読者が誤解しやすい言い回しの有無\n\n"
            "## 追加で集めたい材料\n"
            f"{_bullets(brief.reference_notes, '自身の経験メモ、実績、観測した変化の記録')}\n\n"
            "## 不確実性の管理\n"
            f"{_bullets(brief.supporting_data, '根拠が不足する箇所は推測として明示する')}\n"
        )

    def _outliner(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        sections = brief.sections_to_cover or [
            "導入: 読者の悩みを具体化する",
            "背景: なぜ今このテーマが重要なのかを整理する",
            "実践: 試して効果があった考え方や手順を示す",
            "まとめ: 今日から始める一歩に落とし込む",
        ]
        numbered = "\n".join(f"{index}. {section}" for index, section in enumerate(sections, start=1))
        return (
            "# 記事構成案\n\n"
            "## 章立て\n"
            f"{numbered}\n\n"
            "## 文章運びの指針\n"
            "- 各節の冒頭で読者の疑問を明示する\n"
            "- 中盤で具体例を挟み、抽象論だけにしない\n"
            "- 終盤で行動提案までつなげる\n"
        )

    def _drafter(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        title = f"{brief.topic}を前に進めるために、最初に整理したいこと"
        keywords = "、".join(brief.keywords[:3]) if brief.keywords else brief.topic
        primary_reader = _primary_reader(brief)
        return (
            "# 記事初稿\n\n"
            f"# {title}\n\n"
            f"{primary_reader}に向けて、{brief.topic}をどう捉え直すと動きやすくなるのかを整理します。"
            f"この記事では、{brief.objective}につながる考え方を、抽象論だけでなく実践の粒度まで落として共有します。\n\n"
            "## まず、つまずきの正体を言語化する\n"
            f"{brief.topic}で止まってしまう理由は、やる気の不足というより、何を優先すべきかが見えにくいからです。"
            "選択肢が多いテーマほど、最初の一歩は曖昧になります。\n\n"
            "## 重要なのは、上手くやることより見立てを持つこと\n"
            f"私が重視したいのは、『{brief.objective}』に直結する見立てを持つことです。"
            "手段を増やす前に、読者が何に困っていて、何を持ち帰れると満足するのかを先に定義します。\n\n"
            "## 小さく試せる形に分解する\n"
            f"{brief.topic}を前に進めるときは、完璧な設計よりも、小さく試して観察できる単位まで分解するのが有効です。"
            "たとえば導入、実践、振り返りの3段で考えると、行動に移しやすくなります。\n\n"
            "## 読後に残したいこと\n"
            f"大切なのは、{keywords}を増やすことではなく、自分なりの判断軸を持つことです。"
            f"{brief.call_to_action or '次に試す一歩を一つ決めて、実際に動いてみてください。'}\n"
        )

    def _reviewer(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        return (
            "# レビュー指摘書\n\n"
            "## 良い点\n"
            "- 読者課題から入り、記事の目的がぶれていない\n"
            "- Note向けに、語り口が硬くなりすぎていない\n\n"
            "## 優先修正事項\n"
            "1. 実践パートの具体例をもう一段増やす\n"
            "2. 根拠が体験ベースなのか一般論なのかを文中で明示する\n"
            "3. 終盤のCTAを、読者が今日やる行動に寄せて具体化する\n\n"
            "## 公開前チェック\n"
            f"{_bullets(brief.constraints, '断定表現と誤読余地を見直す')}\n"
        )

    def _final_editor(self, brief: ArticleBrief, stage_results: dict[str, StageResult]) -> str:
        title = f"{brief.topic}を前に進めるときに、最初に整えたい判断軸"
        tags = brief.keywords[:3] if brief.keywords else [brief.topic, "note", "執筆"]
        clean_tags = [re.sub(r"\s+", "", item) for item in tags if item.strip()]
        hashtags = " ".join(f"#{item}" for item in clean_tags)
        primary_reader = _primary_reader(brief)
        return (
            f"# {title}\n\n"
            f"{primary_reader}として{brief.topic}に向き合うとき、最初に難しいのは『何から考えればいいのか』が見えないことです。"
            f"今回は、{brief.objective}につなげるために、私が先に整えておきたい判断軸をまとめます。\n\n"
            "## 1. まず、課題を曖昧なままにしない\n"
            f"{brief.topic}に関する悩みは、手段の不足ではなく、課題設定の曖昧さから生まれることが少なくありません。"
            "だからこそ、最初に『自分は何を前に進めたいのか』を短く言語化します。\n\n"
            "## 2. 再現できる単位まで分解する\n"
            "大きなテーマをそのまま抱えると、情報収集だけで終わりがちです。"
            "導入、実践、振り返りのように小さな単位へ分解すると、試行回数を増やしやすくなります。\n\n"
            "## 3. うまくいった理由を記録する\n"
            "一度前に進めたことは、結果だけでなく理由も書き残しておくと、次の判断が速くなります。"
            "自分の言葉で整理した記録は、そのまま読者への価値にもなります。\n\n"
            "## まとめ\n"
            f"{brief.topic}を進めるときに必要なのは、派手な正解よりも、{brief.objective}に向かうための小さな判断軸です。"
            f"{brief.call_to_action or 'この記事を閉じたら、まずは次に試す一歩を一つだけ決めてみてください。'}\n\n"
            "## 想定ハッシュタグ\n"
            f"{hashtags}\n"
        )


def build_runner(mode: str, command: str | None = None) -> BaseRunner:
    normalized = mode.lower()
    if normalized == "manual":
        return ManualRunner()
    if normalized == "mock":
        return MockRunner()
    if normalized == "command":
        if not command:
            raise ValueError("--command is required when mode=command")
        return CommandRunner(command)
    raise ValueError(f"unsupported mode: {mode}")
