# Operations

この文書は、`このプロジェクトを止めずに回すための運用手順` をまとめたものです。機能仕様ではなく、継続公開の実務を対象にします。

## 運用モード

### 手動モード

用途:

- 新テーマの立ち上げ
- 重要記事の重点執筆
- 自動化前の品質確認

主なコマンド:

```bash
python3 run_note_team.py validate
python3 run_note_team.py run --brief examples/brief.sample.json --mode mock
```

### 自動モード

用途:

- 4時間ごとの最新記事生成
- 公開面の継続更新
- 重複回避を前提にした記事資産の拡張

主なコマンド:

```bash
python3 run_note_team.py autopilot \
  --catalog config/topic_catalog.json \
  --team config/note_editorial_team.json \
  --content-root content \
  --output-root runs \
  --mode command \
  --runner-command "your-llm-cli --model {model} --reasoning {reasoning_effort} --stdin"
```

## 定期実行

GitHub Actions では `.github/workflows/automation_cycle.yml` を使い、`4時間ごと` に自動運転を回します。

必要な前提:

- `NOTE_TEAM_RUNNER_COMMAND` を repository secret に設定していること
- runner command から利用する外部 LLM が安定していること
- `content/` と `publish_site/` を commit できること

## 運用担当が見るべき場所

- `runs/`: 個別の執筆実行結果
- `automation/briefs/`: 自動生成された執筆指示
- `automation/runs/`: 自動運転の結果記録
- `automation/daily_coverage/`: 公開対象テーマの当日カバレッジ
- `content/`: 公開記事
- `publish_site/`: 配信物

## 公開対象テーマ

現在の `Note Multi-Agent Blog` 公開対象は次です。

- `ベビー`
- `Gemini / GPT / Claude比較`
- `Claude活用`
- `業界別DX・AI導入事例ウォッチ`
- `防災DX`
- `Apple製品`
- `テニス練習メニュー`

## 日次運用

- `python scripts/check_daily_theme_coverage.py` を実行し、今日の記事が未作成のテーマを確認する
- 新しく追加された記事タイトルを一覧で確認する
- 既存記事と似すぎていないかを確認する
- 公開面のカテゴリバランスを確認する
- 事実が古くなりやすい記事を更新候補へ入れる
- `QUALITY_GATE_REPORT.md` の fail を確認する
- `SCORECARD.md` の低スコア記事を確認する

## 週次運用

- テーマ別の本数偏りを確認する
- `topic_catalog.json` の自動化対象を見直す
- `preferred_domains` の追加や削除を行う
- モデルの配分が過剰コストになっていないか確認する
- `docs/project-issue-board.md` の P0 / P1 を更新する

## 月次運用

- 公開面の導線改善
- 古い記事の再編集や統合判断
- 重複傾向の分析
- docs と README の同期確認
- テーマ棚卸しを行い、止めるテーマと伸ばすテーマを決める

## 今日の記事の欠損を点検する

日次ジョブでは `scripts/check_daily_theme_coverage.py` を使い、公開対象テーマごとに `今日の日付の記事が存在するか` を点検します。

```bash
python scripts/check_daily_theme_coverage.py
```

出力:

- `automation/daily_coverage/YYYY-MM-DD.json`
- `automation/daily_coverage/YYYY-MM-DD.md`

このレポートを見れば、手作業で `content/` を横断せずに、未作成テーマだけを補完できます。

## 失敗時の復旧手順

### フィード取得に失敗した場合

- 対象 URL が生きているか確認する
- 一時的なネットワーク失敗か確認する
- 代替フィードを `topic_catalog.json` に追加する

### 重複判定で記事候補が消える場合

- 同じテーマに偏りすぎていないか確認する
- `max-age-hours` を広げる
- テーマの粒度や切り口を見直す
- 更新記事として扱うべき候補が新規候補になっていないか確認する

### runner command が失敗する場合

- シークレットの値を確認する
- `{model}` `{reasoning_effort}` などの埋め込み変数を確認する
- CLI の標準入力仕様が合っているか確認する

### 公開面生成が失敗する場合

- `scripts/build_publish_site.py` を単体実行する
- 問題の記事 Markdown に壊れた構文がないか確認する
- `config/topic_catalog.json` の `output_dir` と実ディレクトリの整合性を確認する

## テーマ追加の手順

新テーマを追加するときは次をそろえます。

1. `config/topic_catalog.json` にテーマを追加
2. `output_dir` を決める
3. 自動化対象なら `feed_urls` と `preferred_domains` を追加
4. 必要なら brief テンプレートや制約を見直す
5. `publish_site/` でカテゴリ導線が壊れないか確認する

## 防災DXテーマの運用メモ

`防災DX` は、国・自治体・民間・生活者の動きが混ざるため、単発ニュースより `構造変化` を拾う運用が重要です。

特に見るべき観点:

- 国の制度、指針、予算、ガイドライン
- 自治体の実装事例
- 民間のプロダクト、インフラ、通信、避難支援
- 世間の受容、課題、普及の壁

このテーマは断片ニュースの焼き直しになりやすいので、review 時に `誰にどんな運用変更を迫る話か` まで落ちているかを確認します。

## 運用品質を落とさないためのルール

- docs を実装と一緒に更新する
- 新しい自動化を足したら `output-format` と `operations` を先に更新する
- 記事本数よりもカテゴリ全体の価値を優先する
- 同じトピックで量産しすぎない
- 品質ゲート未達なら指揮担当が自動公開停止を判断する
