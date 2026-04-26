# Workflow

このプロジェクトの workflow は、`記事を1本作る流れ` と `継続公開を回す流れ` の2本立てです。どちらも最終的には同じ編集ステージを通るため、品質基準を統一できます。

## 1. 通常の執筆フロー

### Step 1. brief を用意する

最低限、次を brief に含めます。

- `topic`
- `objective`
- `target_reader`

品質を上げるには、さらに次を入れます。

- `angle`
- `tone`
- `constraints`
- `reference_notes`
- `sections_to_cover`
- `supporting_data`

### Step 2. validate する

```bash
python3 run_note_team.py validate
```

設定ファイル、依存関係、prompt パス、モデルプロファイルの破綻を先に検知します。

### Step 3. run する

```bash
python3 run_note_team.py run \
  --brief examples/brief.sample.json \
  --mode command \
  --runner-command "your-llm-cli --model {model} --reasoning {reasoning_effort} --stdin"
```

`WorkflowRunner` が各ステージを順番に実行し、`runs/<timestamp>-<slug>/` に成果物を残します。

### Step 4. 最終稿を確定する

公開対象は `FINAL_ARTICLE.md` です。必要があれば各ステージの `response.md` を見て、どこで論点が崩れたかを戻り調整します。

## 2. 編集ステージの流れ

```text
brief
  -> command_lead
  -> editor_in_chief
  -> strategy
  -> research
  -> outline
  -> draft
  -> fact_review
  -> editorial_review
  -> final_edit
  -> FINAL_ARTICLE.md
```

各ステージの基本役割は次のとおりです。

- `command_lead`: 何が課題か、どれを先に潰すか、誰が持つかを決める
- `editor_in_chief`: 何を良しとするかを決める
- `strategy`: どう刺すかを決める
- `research`: 何を根拠に書くかを固める
- `outline`: どう並べるかを決める
- `draft`: 文章化する
- `fact_review`: 事実と根拠の欠陥を見つける
- `editorial_review`: 読みやすさと重複の欠陥を見つける
- `final_edit`: 公開品質に整える

## 2.1 課題管理表を先に作る

この workflow では、執筆前に必ず `課題管理表` を作ります。目的は、全員が同じ危険箇所と優先順位を見た上で動くことです。

run ごとに `ISSUE_BOARD.md` を生成し、少なくとも次を管理します。

- `P0`: 公開できない重大欠陥
- `P1`: 記事価値を大きく下げる課題
- `P2`: 品質を底上げする改善課題

課題管理表には、次の列を持たせます。

- `priority`
- `issue`
- `owner`
- `target_stage`
- `status`
- `close_condition`

指揮担当はこの表を起点に各工程へ指示を出し、編集長以降の工程は自工程の成果物だけでなく、担当課題を潰せたかで評価します。

## 3. モデル選択の流れ

モデルは固定ではなく、`agent × content` の組み合わせで解決します。

1. 各エージェントに `model_profile` を設定する
2. `default_model_profile` を fallback にする
3. brief のキーワードに応じて `content_overrides` を適用する

これにより、軽い企画は速く、最新性や高リスク領域の review は慎重に、という配分ができます。

## 4. 自動執筆フロー

`autopilot` は定期更新（標準は4時間ごと）を前提に設計しています。現在は GitHub Actions 側で `schedule` を停止しており、`workflow_dispatch` での手動起動のみ動きます。

```text
topic catalog
  -> recent feed collection
  -> duplicate screening
  -> update or new decision
  -> research cache lookup
  -> generated brief
  -> editorial workflow
  -> content/ へ配置
  -> publish_site/ 再生成
  -> automation/runs/ へ記録
```

実行例:

```bash
python3 run_note_team.py autopilot \
  --catalog config/topic_catalog.json \
  --team config/note_editorial_team.json \
  --content-root content \
  --output-root runs \
  --mode command \
  --runner-command "your-llm-cli --model {model} --reasoning {reasoning_effort} --stdin" \
  --max-age-hours 8
```

## 5. 自動執筆で何を見ているか

自動運転では、単に新着ニュースを拾って記事化するのではなく、次を同時に見ています。

- 鮮度: `max-age-hours` 以内の情報か
- 信頼度: 優先ドメインに近いか
- 独自性: 既存記事と切り口が近すぎないか
- 更新向きか: 既存記事の差分更新で扱うべきか

`topic_catalog.json` にある `preferred_domains` は、`国・公式・主要ベンダー` をやや優先するための重み付けとして使います。

## 6. 重複防止の workflow

重複防止は運用の中心です。1年以上回す前提では、ここを曖昧にすると記事群の価値が急激に下がります。

現在の流れは次のとおりです。

1. `content/` から既存記事のタイトルと要約を読む
2. 新しい候補記事タイトルとの類似度を計算する
3. 閾値以上なら候補から除外する
4. 近い既存記事を brief に埋め込み、執筆時にも回避させる

この二重の防御により、`同じニュースを別見出しで焼き直すだけ` の状態を避けます。

## 6.1 更新記事と新規記事の分岐

自動運転では、候補が既存記事に十分近い場合は `新規記事` ではなく `更新記事` として扱います。

- 類似度が低い: 新規記事
- 類似度が中程度: 既存記事の更新候補
- 類似度が高い: 候補除外

これにより、資産価値が薄い量産を避けます。

## 7. 公開 workflow

### Note Multi-Agent Blog

1. `content/` に Markdown を配置する
2. `scripts/build_publish_site.py` で HTML を再生成する
3. `publish_site/` を GitHub Pages などで配信する

## 8. GitHub Actions での定期実行

`.github/workflows/automation_cycle.yml` は `workflow_dispatch`（手動）と任意の `schedule` で次を実行する構成です。

1. リポジトリを checkout
2. Python 依存をインストール
3. `autopilot` を実行
4. 変更があれば `content publish_site automation runs` を commit して push

現在は repository secret `NOTE_TEAM_RUNNER_COMMAND` が未登録のため、`schedule` トリガーは外し手動実行のみにしています。定期実行に戻すときは secret を登録した上で `on:` に `schedule: - cron: '0 */4 * * *'` を追記してください。

## 9. 失敗時の扱い

自動運転が失敗しても、原因が追えるように次を残します。

- 生成 brief
- `runs/` のステージ成果物
- `automation/runs/` の記録

運用では次の順で確認します。

1. フィードが取れているか
2. 重複判定で全候補が落ちていないか
3. runner command が有効か
4. モデル切替設定が意図どおりか
5. `build_publish_site.py` が落ちていないか

## 10. 推奨する運用リズム

- 4時間ごと: 自動執筆と公開面更新（secret 登録後に `schedule` を再有効化することを前提）
- 毎日: `automation/daily_coverage/` で未作成テーマを確認し、欠損分だけ補完する
- 毎週: 重複傾向とカテゴリ偏りの確認
- 毎月: テーマカタログとモデルプロファイルの見直し
