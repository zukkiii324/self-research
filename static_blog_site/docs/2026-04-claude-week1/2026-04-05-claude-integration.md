# Claudeを既存ツールに素早く組み込むポイント

4月5日は、Claudeを社内ツールやSlack/Notionに組み込む際の実装ポイントです。Claude 3 はAPI経由での接続時に `response_format` をJSONで指定できるため、パイプラインへの組み込みが非常にスムーズです。

## Slack/Teams連携

1. Slack Appを通じて Claude Kernel を呼び出す際、まず slash コマンドで「プロジェクト名／質問カテゴリ／ファイル添付可否」をCollect
2. Claudeには `channel` `requester` `context_url` を渡し、出力内に `【回答】` `【補足】` `【次のアクション】` のブロックを含めさせる
3. Botが出力を受け取った後、自動で `@channel` への summary メッセージを1文追加し、出力の `next_action` をタスクボードに転記

## Notion/Confluence

- Claudeの出力を Notion のテンプレートデータベースに送るときは、もう一度 `自然言語要約` → `構造化マップ` の2段階で整備するとレビューしやすい
- APIのレスポンスには `source="Claude"` `prompt_id` `session_id` を含め、出典のトレーサビリティを持たせる
- 定期的に出力を Notion に push するバッチは、出力先が期待値から逸脱したらSlackで管理者へ通知する仕組みにしておく

## 監査ログ

Claudeをツールに組み込むときの必須要件は、**出力の再現性と追跡性**です。必ず次を記録しておきましょう。

- 使用した `prompt_id`/`template_name`
- `session_id`/`conversation_id`
- `requester`/`channel`
- `response_format`

これらが揃っていれば、後から「どのプロンプトでどんな回答が出たか」「どんなデータが入力されたか」がすぐに遡れます。
