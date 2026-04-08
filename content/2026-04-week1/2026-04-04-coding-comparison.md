# コーディング支援でGemini / GPT / Claudeをどう使い分けるか

コーディングでは、モデル単体の精度差より `どの作業を切り出すか` が重要です。

## まず役割分担

- `GPT`: 実装案、デバッグ方針、試作コード
- `Gemini`: Google開発基盤やドキュメント周辺の補助
- `Claude`: 大きめのコード変更、レビュー、説明整理

## GPTは試行錯誤の速さが強み

OpenAIのChatGPT Plus / Team系では、複数モデルやagent、projects、data analysisなどがまとまっています。  
このため、実装の入口で「まず試す」用途と相性が良いです。

向いている場面:

- エラー原因の仮説出し
- 小さな関数の下書き
- 設計案の比較

## GeminiはGoogle開発環境との相性を見る

GeminiはWorkspace寄りの印象が強い一方で、Google環境の情報整理と並行して開発を進める時に扱いやすいです。  
仕様メモ、Docs、Gmail、Meetの流れの中で開発タスクを動かすチームなら、Geminiの位置づけは明確です。

向いている場面:

- 仕様確認と実装メモを往復する
- 会議メモからタスクを整える
- Google資産前提の社内開発

## Claudeは大きめの差分説明に向く

Claudeは長文処理とProjectsが強いので、変更規模が大きいときに価値が出やすいです。  
コードそのものだけでなく、「なぜこの構成にするか」を文章で整える場面と相性があります。

向いている場面:

- 複数ファイル変更の要約
- 大きな差分のレビュー補助
- 実装方針の説明文作成

## 実務での置き方

1. GPTで仮説と試作
2. Geminiで周辺ドキュメント確認
3. Claudeで大きい差分を整理

この並びにすると、速さと安定感を両立しやすいです。

## 注意点

どのモデルでも、`実行結果の確認` は別です。  
コーディング支援は速くなりますが、検証を省略してはいけません。

## 参考

- [OpenAI Pricing](https://openai.com/pricing)
- [Manage your Google AI plan from Gemini Apps](https://support.google.com/gemini/answer/14517446?hl=en)
- [Gemini for Google Workspace now supports additional languages](https://workspace.google.com/blog/product-announcements/gemini-google-workspace-now-supports-additional-languages)
- [Claude Pricing](https://website.claude.com/pricing)
