# Note Multi-Agent Writing Project

`Note Multi-Agent Blog` 向けの記事制作と公開を、複数エージェントの編集組織で進めるローカル向けプロジェクトです。

案件ブリーフを 1 つ投入すると、各エージェントが順番に成果物を作成し、`runs/<timestamp>-<slug>/` 配下に保存します。最終的には `FINAL_ARTICLE.md` に公開直前の原稿を出力します。

## 何ができるか

- 記事テーマから公開用原稿までの作業を分業できます。
- 役割ごとに責務を分けるので、調査漏れや構成の粗さを減らせます。
- すべての中間成果物が `runs/<slug>/` に残るため、あとから検証しやすいです。

## 想定する役割

- 指揮担当: 課題整理、優先順位付け、進行統率
- 編集長: 全体方針と品質基準の定義
- 戦略: 読者設定、切り口、訴求設計
- リサーチ: 事実確認、参考情報収集、一次情報整理
- 構成: 見出し設計、論理順、記事の骨組み作成
- ドラフト: 本文の初稿作成
- 事実レビュー: 根拠、最新性、断定リスクを点検
- 編集レビュー: 読みやすさ、重複、構成の粗さを点検
- 最終編集: 文体統一、冗長表現の削除、公開直前の整形

## 成果物の流れ

1. ブリーフを入力する
2. 指揮担当が課題と優先順位を定める
3. 編集長が企画方針を定める
4. 戦略が狙いを固める
5. リサーチが材料を整理する
6. 構成が記事の骨格を作る
7. ドラフトが本文を書く
8. 事実レビューが根拠の穴を返す
9. 編集レビューが可読性と重複を返す
10. 最終編集が公開品質に整える

## 出力先

各実行は次のような構成です。

```text
runs/<timestamp>-<slug>/
  01-command_lead/
    prompt.md
    response.md
  02-editor_in_chief/
    prompt.md
    response.md
  03-strategy/
    prompt.md
    response.md
  ...
  08-editorial_review/
    prompt.md
    response.md
  09-final_edit/
    prompt.md
    response.md
  snapshots/
    brief.json
    team.json
  ISSUE_BOARD.md
  QUALITY_GATE_REPORT.md
  SCORECARD.md
  FINAL_ARTICLE.md
  RUN_SUMMARY.md
  manifest.json
```

`<slug>` は案件名をファイル名向けに整形した識別子です。日本語テーマだけでも動きますが、CLI は安全な ASCII slug を自動生成します。

## 使い方

そのまま実行するなら、ルートの `run_note_team.py` を使います。パッケージとして入れる場合は `pip install -e .` 後に `note-team` コマンドでも実行できます。

```bash
python3 run_note_team.py validate
python3 run_note_team.py run --brief examples/brief.sample.json --mode mock
```

外部LLMを実際に叩く場合は `command` モードを使います。各ステージの `prompt.md` を標準入力で渡し、その標準出力を `response.md` として保存します。

```bash
python3 run_note_team.py run \
  --brief examples/brief.sample.json \
  --mode command \
  --runner-command "your-llm-cli --model {model} --reasoning {reasoning_effort} --stdin"
```

`mock` モードは構成確認用です。実運用では `command` モードで任意のLLM CLIを差し込む想定です。

## モデル自動選択

チーム設定 `config/note_editorial_team.json` では、各エージェントに `model_profile` を割り当てられます。プロファイルには少なくとも次を持たせます。

- `model`: 実際に使うモデル名
- `reasoning_effort`: 推論の深さ
- `notes`: そのプロファイルの用途メモ

さらに `content_overrides` を使うと、ブリーフ内に特定キーワードがある場合だけ、特定工程を強いモデルへ切り替えられます。現行設定では `医療` `法律` `投資` `最新` などを含む案件で、`research` `review` `final_edit` が精度優先プロファイルへ上書きされます。

`--runner-command` には次の変数を埋め込めます。

- `{model}`
- `{reasoning_effort}`
- `{model_profile}`
- `{agent_id}`
- `{agent_name}`
- `{department}`
- `{deliverable}`

例:

```bash
python3 run_note_team.py run \
  --brief examples/brief.sample.json \
  --mode command \
  --runner-command "my-llm-cli --model {model} --effort {reasoning_effort} --stage {agent_id} --stdin"
```

## ドキュメント

- [設計概要](docs/architecture.md)
- [役割定義](docs/roles.md)
- [実行フロー](docs/workflow.md)
- [出力フォーマット](docs/output-format.md)

## ブログの自動公開

1. `scripts/build_publish_site.py` を使い、`content/` 配下の Markdown から `publish_site/` を再生成します。

   ```bash
   python3 scripts/build_publish_site.py
   ```

2. GitHub Actions (`.github/workflows/deploy_static_blog.yml`) は `publish_site/` を `gh-pages` ブランチへ配信します。現在は自動公開を停止し、`workflow_dispatch` での手動実行のみ受け付ける構成です。再開するには `on:` に `push:` トリガー（旧 `paths` フィルタ）を戻してください。

3. `.github/workflows/automation_cycle.yml` は `autopilot` を実行し、`content/` と `publish_site/` を更新して `main` へ commit します。現在は手動実行 (`workflow_dispatch`) のみで、定期実行は停止しています。再開には repository secret `NOTE_TEAM_RUNNER_COMMAND` の登録と、`schedule` トリガー (`cron: '0 */4 * * *'` など) の追記が必要です。

4. GitHub Pages 側の設定（Settings → Pages で `gh-pages` ブランチをソース指定）を行えば、`Note Multi-Agent Blog` が継続的に更新されます。

## 公開対象テーマ

現在の公開対象カテゴリは次です。

- `ベビー`
- `Gemini / GPT / Claude比較`
- `Claude活用`
- `業界別DX・AI導入事例ウォッチ`
- `防災DX`
- `Apple製品`
- `テニス練習メニュー`

`scripts/check_daily_theme_coverage.py` は、公開対象テーマについて `今日の記事があるか` を点検し、`automation/daily_coverage/` にレポートを保存します。GitHub Actions (`daily_theme_coverage.yml`) は現在 `workflow_dispatch` のみで、定期実行は停止しています。
