# Note Multi-Agent Writing Project

`Note` 向けの記事制作を、複数エージェントの編集組織で進めるローカル向けプロジェクトです。

この公開リポジトリは、生成済みコンテンツを静的ブログとして GitHub Pages へ自動デプロイする最小構成を含みます。

## 含まれるもの

- `content/` に置いた記事 Markdown
- `scripts/build_static_blog.py` による MkDocs 用 `docs/` 再生成
- `.github/workflows/deploy_static_blog.yml` による GitHub Pages 自動デプロイ

## 公開フロー

```bash
python3 scripts/build_static_blog.py
```

その後 `main` へ push すると、GitHub Actions が `gh-pages` ブランチへ静的サイトをデプロイします。
