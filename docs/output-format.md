# Output Format

このプロジェクトでは、`何が生成されたか` だけでなく、`なぜそうなったか` をあとから追えることを重視しています。そのため出力は単一ファイルではなく、実行単位、公開単位、自動運転単位で分けて保存します。

## 1. run 単位の成果物

標準の執筆実行は `runs/<timestamp>-<slug>/` に保存されます。

```text
runs/20260408-010203-sample-topic/
  01-command_lead/
    prompt.md
    response.md
  02-editor_in_chief/
    prompt.md
    response.md
  03-strategy/
    prompt.md
    response.md
  04-research/
    prompt.md
    response.md
  05-outline/
    prompt.md
    response.md
  06-draft/
    prompt.md
    response.md
  07-fact_review/
    prompt.md
    response.md
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
  FINAL_ARTICLE.md
  RUN_SUMMARY.md
  manifest.json
```

## 2. 各ファイルの意味

### `prompt.md`

そのステージに与えた最終 prompt です。`brief` と前工程の要約が反映された、実際の入力を保存します。

### `response.md`

そのステージの出力本文です。中間生成物として保存され、後続ステージの入力にもなります。

### `snapshots/brief.json`

実行時点で使った brief の固定コピーです。あとから元ファイルが更新されても、実行時の条件を再現できます。

### `snapshots/team.json`

チーム設定の固定コピーです。モデルプロファイルや役割定義を後から変えても、当時の設定を参照できます。

### `FINAL_ARTICLE.md`

公開候補として扱う最終稿です。通常は `final_edit` の出力をここへ固定します。

### `RUN_SUMMARY.md`

人間が素早く読むための要約です。テーマ、目的、対象読者、各ステージの出力位置、モデル割当を確認できます。

### `ISSUE_BOARD.md`

run ごとの課題管理表です。指揮担当が定義した優先順位、担当、完了条件を保存します。

### `QUALITY_GATE_REPORT.md`

数値化した品質ゲートの判定結果です。参考リンク数、一次情報比率、要約長、見出し重複などを run 単位で確認できます。

### `SCORECARD.md`

正確性、独自性、可読性、公開完成度を 5 段階で保存するスコアカードです。

### `manifest.json`

機械処理向けのメタデータです。後続の自動化や分析に使います。

## 3. `manifest.json` の主な項目

現在の `manifest.json` には少なくとも次が入ります。

- `workflow`
- `mode`
- `brief_topic`
- `run_dir`
- `stages`
- `final_article_path`

各 `stages[]` には次を格納します。

- `id`
- `name`
- `deliverable`
- `prompt_path`
- `response_path`
- `model_profile`
- `model`
- `reasoning_effort`

これにより、`どのステージでどのモデルを使ったか` まで追跡できます。

## 4. 公開記事の保存先

公開済みまたは公開候補の記事は `content/` に置きます。

```text
content/
  2026-04-baby-week1/
  2026-04-week1/
  2026-04-claude-week1/
  disaster-dx-watch/
```

テーマごとの出力先は `config/topic_catalog.json` の `output_dir` で管理します。

各ディレクトリには通常、次が入ります。

- 日付付き Markdown 記事
- `README.md`

## 5. 自動運転の成果物

自動執筆では `automation/` 配下にも成果物が残ります。

```text
automation/
  briefs/
    20260408-030000-auto-topic.json
  runs/
    20260408-030500-disaster_dx.json
```

### `automation/briefs/*.json`

フィードから生成した brief です。人手で書いた brief ではなく、自動選定ロジックが作った執筆指示を保存します。

### `automation/runs/*.json`

自動運転1回分の結果です。主に次を持ちます。

- `topic_id`
- `topic_label`
- `source_title`
- `source_url`
- `brief_path`
- `run_dir`
- `published_path`
- `status`
- `article_mode`

## 6. 静的サイトの成果物

静的ブログの配信用ファイルは `publish_site/` に出力します。

```text
publish_site/
  index.html
  .nojekyll
  baby/
    index.html
  ai_practical/
    index.html
  claude/
    index.html
  industry_dx_ai_watch/
    index.html
  disaster_dx/
    index.html
  apple_products/
    index.html
  tennis_menu/
    index.html
```

この構造により、トップページで横断検索しつつ、カテゴリページでまとめ読みできるようにしています。

## 7. 出力の使い分け

用途ごとに見る場所を分けるのが基本です。

- 記事本文を見たい: `content/` または `FINAL_ARTICLE.md`
- 生成経路を見たい: `runs/`
- 自動運転の判断を見たい: `automation/`
- 公開HTMLを見たい: `publish_site/`

## 8. 追跡性の価値

この出力設計により、次の改善がしやすくなります。

- どの brief から良い記事が出たか比較できる
- どのステージで品質が落ちたか追える
- どのモデル配分が有効だったか比較できる
- 自動化の重複回避が効いているか検証できる
- 公開済みコンテンツ資産を再利用しやすい
