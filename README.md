# Note Multi-Agent Writing Project

`Note` 向けの記事制作を、複数エージェントの編集組織で進めるローカル向けプロジェクトです。

案件ブリーフを 1 つ投入すると、各エージェントが順番に成果物を作成し、`runs/<timestamp>-<slug>/` 配下に保存します。最終的には `FINAL_ARTICLE.md` に公開直前の原稿を出力します。

## 何ができるか

- 記事テーマから公開用原稿までの作業を分業できます。
- 役割ごとに責務を分けるので、調査漏れや構成の粗さを減らせます。
- すべての中間成果物が `runs/<slug>/` に残るため、あとから検証しやすいです。

## 想定する役割

- 編集長: 全体方針と品質基準の定義
- 戦略: 読者設定、切り口、訴求設計
- リサーチ: 事実確認、参考情報収集、一次情報整理
- 構成: 見出し設計、論理順、記事の骨組み作成
- ドラフト: 本文の初稿作成
- レビュー: 事実性、読みやすさ、論理の穴を指摘
- 最終編集: 文体統一、冗長表現の削除、公開直前の整形

## 成果物の流れ

1. ブリーフを入力する
2. 編集長が企画方針を定める
3. 戦略が狙いを固める
4. リサーチが材料を整理する
5. 構成が記事の骨格を作る
6. ドラフトが本文を書く
7. レビューが問題点を返す
8. 最終編集が公開品質に整える

## 出力先

各実行は次のような構成です。

```text
runs/<timestamp>-<slug>/
  01-editor_in_chief/
    prompt.md
    response.md
  02-strategy/
    prompt.md
    response.md
  ...
  07-final_edit/
    prompt.md
    response.md
  snapshots/
    brief.json
    team.json
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

## noteへの自動投稿準備

1. 依存ライブラリをインストールします（Playwrightとブラウザ）:

   ```bash
   pip install playwright
   playwright install chromium
   ```

2. `queues/drafts/` にある JSON を `scripts/publish_note_draft.py` で読み、noteのUIを操作して下書き保存します。

   - 環境変数 `NOTE_EMAIL` / `NOTE_PASSWORD` を設定
   - `NOTE_PREVIEW_URL` などは今のところ不要（将来の追加で対応可能）
   - `--headless` でヘッドレス実行

   ```bash
   NOTE_EMAIL=xxx NOTE_PASSWORD=yyy python3 scripts/publish_note_draft.py
   ```

3. 成功すると `queues/drafts/*.json` が `status=draft_created` に更新され、`note_url` に保存先が入ります。

4. 一度にたくさん予約したい場合は `scripts/stage_note_draft.py` で JSON をためておき、スクリプトを定期的に呼び出します。

**補足:** noteのUIは変更されやすいため、`scripts/publish_note_draft.py` のセレクター（タイトル・本文・タグ・下書き保存ボタン）は適宜更新してください。自動化が失敗したら `HEADLESS=false` で起動して手動トレースをすると原因がわかりやすいです。

## 静的ブログの自動公開

1. `scripts/build_static_blog.py` を使い、`content/` 配下の Markdown を `static_blog_site/docs/` にコピー＋`index.md` を再生成します。

   ```bash
   python3 scripts/build_static_blog.py
   ```

2. `mkdocs` によるビルドは GitHub Actions (`.github/workflows/deploy_static_blog.yml`) が担い、`site` ディレクトリを生成して `peaceiris/actions-gh-pages` で `gh-pages` ブランチへデプロイします。

3. `static_blog_site/mkdocs.yml` にデフォルトテーマを定義しています。必要があれば `theme:` や `extra:` を調整してください。

4. GitHub Pages 側の設定（リポジトリの Settings → Pages で `gh-pages` ブランチをソース指定）を行えば、push するだけで自動公開されるようになります。

5. GitHub リモートがない場合は、`git init` → リモートを追加（例: `git remote add origin git@github.com:<user>/note-test.git`）→ `git push -u origin main` の流れで初回公開してください。
