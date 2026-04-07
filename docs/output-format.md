# Output Format

`runs/<timestamp>-<slug>/` には、工程ごとのディレクトリと全体サマリを保存します。

## 実際の出力

- `01-editor_in_chief/prompt.md`
- `01-editor_in_chief/response.md`
- `02-strategy/prompt.md`
- `02-strategy/response.md`
- `...`
- `07-final_edit/prompt.md`
- `07-final_edit/response.md`
- `snapshots/brief.json`
- `snapshots/team.json`
- `FINAL_ARTICLE.md`
- `RUN_SUMMARY.md`
- `manifest.json`

## 例

```text
runs/20260408-010203-how-to-write-on-note/
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

## メタデータ

`manifest.json` には、少なくとも次の情報が入ります。

- `workflow`
- `mode`
- `brief_topic`
- `run_dir`
- `stages`
- `final_article_path`
