# Architecture

このプロジェクトは、`1本の記事を書くツール` ではなく、`企画・調査・執筆・レビュー・公開運用を分業する編集システム` として設計しています。単発生成よりも、再現性、追跡性、重複回避、公開継続性を優先します。

## 設計原則

- 役割ごとに責務を固定し、判断の混線を減らす
- すべての中間成果物を保存し、あとから検証できるようにする
- 最終稿の前に必ずレビューと最終編集を入れる
- 1回の実行結果を `run` 単位で閉じ込め、再実行しやすくする
- 記事生成だけで終わらせず、公開面と運用面までつなぐ
- 自動化時でも既存公開記事との重複を避ける

## システム全体像

```text
brief / feed
   |
   v
WorkflowRunner
   |
   +-> command_lead
   +-> editor_in_chief
   +-> strategy
   +-> research
   +-> outline
   +-> draft
   +-> review
   +-> final_edit
   |
   +-> runs/<timestamp>-<slug>/
   |
   +-> content/<topic-output-dir>/*.md
   |
   +-> publish_site/
```

手動実行では `brief` を起点にし、自動実行では `feed` から候補トピックを選んで brief を生成します。どちらも最終的には同じ編集ワークフローを通ります。

## 主要コンポーネント

### CLI

- `run_note_team.py`
- `src/note_team/cli.py`

エントリポイントです。主なサブコマンドは次の2つです。

- `validate`: チーム設定と prompt の整合性確認
- `run`: 指定 brief で通常の執筆ワークフローを実行
- `autopilot`: フィード収集から記事選定、執筆、公開素材更新までを自動実行

### ワークフロー実行

- `src/note_team/orchestrator.py`

`WorkflowRunner` が中核です。brief を読み込み、各エージェントの prompt を組み立て、順番に runner を呼び出し、各ステージの `prompt.md` と `response.md` を保存します。最終エージェントの出力を `FINAL_ARTICLE.md` として固定します。

### モデルと設定

- `src/note_team/models.py`
- `config/note_editorial_team.json`

エージェント定義、モデルプロファイル、コンテンツ上書きルールを持ちます。`model_profiles` と `content_overrides` により、テーマやリスクに応じてモデルを切り替えます。

例:

- 通常案件では `balanced`
- `医療` `法律` `投資` `最新` を含む案件では `research` `review` `final_edit` を精度優先へ切り替え

### 自動運転

- `src/note_team/automation.py`
- `config/topic_catalog.json`
- `.github/workflows/automation_cycle.yml`

自動運転は次の責務を持ちます。

1. テーマカタログから自動化対象テーマを読む
2. RSS / Atom フィードから直近記事候補を集める
3. 既存公開記事との重複スコアを計算する
4. 最も鮮度と独自性が高い候補を選ぶ
5. brief を自動生成する
6. 通常の編集ワークフローで記事化する
7. `content/` と `publish_site/` を更新する
8. `automation/runs/` に実行記録を残す

GitHub Actions では `4時間ごと` にこのサイクルを回す想定でしたが、現在は `workflow_dispatch` のみで動かす運用に変更しています。定期実行を戻すには `automation_cycle.yml` に `schedule` を追記し、repository secret `NOTE_TEAM_RUNNER_COMMAND` を設定してください。

### 公開面

- `scripts/build_publish_site.py`
- `publish_site/`

公開用の静的サイトを生成します。`content/` に置かれた公開済み Markdown を読み、カテゴリページとトップページを構築します。現在は次の価値を重視しています。

- 入口で迷わないカテゴリ導線
- 横断検索しやすい一覧
- 長文でも読みやすい余白とタイポグラフィ
- 記事量が増えても探しやすい構成

## エージェント構成

標準の8役割は次のとおりです。

1. `command_lead`: 課題整理、優先順位付け、進行統率
2. `editor_in_chief`: 企画方針、品質基準、ステージ要求の定義
3. `strategy`: 読者、切り口、差別化の設計
4. `research`: 根拠、事実、公開情報の整理
5. `outline`: 見出し構造と論理順の設計
6. `draft`: 本文の初稿生成
7. `review`: 事実性、論理性、重複、曖昧さの指摘
8. `final_edit`: 公開品質への最終統合

この分割により、`何を集めるか` と `どう書くか` と `何を直すか` を切り離しています。

## データフロー

### 1. 手動執筆

```text
brief.json
  -> WorkflowRunner.run()
  -> runs/<timestamp>-<slug>/
  -> FINAL_ARTICLE.md
```

### 2. 自動執筆

```text
topic_catalog.json
  -> feed collection
  -> duplicate check against content/
  -> generated brief
  -> WorkflowRunner.run()
  -> content/<topic-output-dir>/*.md
  -> build_publish_site.py
  -> publish_site/
```

## 重複回避の考え方

自動化の価値は `量産` ではなく `継続しても劣化しないこと` です。このため `automation.py` では既存記事タイトルと要約を token 化し、新候補との overlap score を計算しています。

- 高い重複スコアの候補は除外
- 近い既存記事は brief に `重複回避対象` として埋め込む
- エージェントには `同じ切り口を繰り返さない` 制約を与える

つまり、重複回避は `候補選定` と `執筆指示` の両方でかけています。

## 品質保証の層

品質は1つの工程で担保せず、多層で持たせています。

- 設定品質: `validate` で設定の破綻を検知
- 入力品質: brief に制約、対象読者、参考情報を明示
- 執筆品質: 役割分担で論点漏れと混線を抑制
- 出力品質: `review` と `final_edit` を必須化
- 運用品質: 既存記事との重複回避、公開面の再構築、実行記録の保存

## ディレクトリ責務

- `config/`: チーム設定、テーマカタログ
- `prompts/`: エージェントごとの指示文
- `src/note_team/`: CLI と実行ロジック
- `runs/`: 1回の執筆実行ごとの成果物
- `content/`: 公開済みまたは公開候補の Markdown
- `publish_site/`: 静的サイトとして配信する成果物
- `automation/`: 自動執筆時の brief と実行ログ
- `docs/`: 設計、運用、品質ルール

## 拡張ポイント

このプロジェクトは次の方向へ拡張しやすい構造です。

- エージェント追加
- テーマごとの別ワークフロー
- モデルルーティングの精緻化
- ソース収集の強化
- 静的サイトの推薦導線や関連記事表示の追加

## いまの強みと制約

強み:

- 中間成果物が揃うため改善点を見つけやすい
- 手動運用と自動運用が同じ基盤で動く
- 公開済み記事を踏まえた重複回避ができる
- モデル切替を設定で制御できる

制約:

- 最新性は runner と参照ソースの品質に依存する
- 重複回避は類似度ベースなので意味的重複を完全には防げない
- モバイル表示や公開面の回 regressions は継続的な検証強化が必要
