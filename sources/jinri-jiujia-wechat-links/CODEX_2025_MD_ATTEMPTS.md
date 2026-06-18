# Codex 2025 WeChat Markdown Attempts

Updated: 2026-06-18

This note records the Codex-generated scripts, intermediate outputs, and known caveats for the 2025 "今日酒价" WeChat Markdown capture and extraction work.

## Context

The goal was to turn verified 2025 `mp.weixin.qq.com` article links from `2025-links.csv` / `2025-links.json` into Markdown snapshots, then extract:

- core Moutai daily price records
- all-product daily price rows
- provenance Markdown for later checking

The source links were already collected and date-validated through the WeChat desktop client account-scoped "今日酒价 发表的文章" search workflow. These scripts do not collect new links.

## Codex runtime caveat

This work was done through Codex desktop conversations. During the work, Codex repeatedly appeared to stop thinking or stop producing output for unclear reasons, even during small local tasks. The cause was not determined.

Possible causes include:

- Codex desktop / terminal bridge instability
- model or tool-call scheduling issues
- local shell / process interaction problems
- bugs or edge cases in the experimental scripts

Because of that, treat these files as Codex-generated attempts and keep auditing outputs carefully before relying on them.

## Added scripts

### `scripts/2025-backfill/fetch_2025_markdown.mjs`

Early batch wrapper around `baoyu-fetch`.

Purpose:

- read `sources/jinri-jiujia-wechat-links/2025-links.json`
- call the baoyu URL-to-Markdown CLI
- save files into `sources/jinri-jiujia-wechat-links/2025-md/YYYY-MM-DD.md`
- keep a state file at `2025-md-state.json`

Known issue:

- `baoyu-fetch` generic adapter was unstable on `mp.weixin.qq.com`.
- It could wait too long or appear stuck around Defuddle / Readability / remote fallback behavior.
- Do not use this script for further bulk WeChat article capture unless specifically debugging baoyu-fetch.

### `scripts/2025-backfill/fetch_2025_markdown_cdp.mjs`

Project-specific Chrome CDP fast path for 2025 links.

Purpose:

- bypass baoyu-fetch generic adapter
- open each WeChat URL through an existing Chrome CDP endpoint
- directly read `#activity-name`, `#js_name`, `#publish_time`, and `#js_content`
- save `#js_content` HTML inside Markdown

Known issue:

- An earlier version could save partial pages when only a few tables had loaded.
- Later output in the formal `2025-md` directory currently audits at 34-35 tables per file, but this script should still be treated cautiously.

### `wechat_mp_fastpath.mjs`

More defensive, reusable WeChat article fast path.

Purpose:

- support JSON, CSV, or single URL input
- connect to an existing Chrome CDP endpoint
- read WeChat article DOM directly
- validate account name, publish date, table count, row count, and stable DOM state before saving

Default quality gates:

- `tables >= 30`
- `rows >= 300`
- `tableCount + rowCount + textLength` stable for 3 consecutive polls
- `publishDate` equals the record date when a date is supplied
- account name defaults to `今日酒价`

Verified sample:

- `2025-09-23` succeeded with 35 tables and 428 rows in a temporary fastpath test output
- `2025-09-22` also succeeded with 35 tables and 428 rows in that temporary fastpath test output

This script is preferred for future retry / continuation work.

### `scripts/2025-backfill/extract_2025_from_markdown.py`

Extractor for saved Markdown snapshots.

Purpose:

- read HTML tables embedded in `sources/jinri-jiujia-wechat-links/2025-md/*.md`
- extract Moutai core daily records to `data-2025.json`
- extract all product rows to `all_prices-2025.jsonl`
- write a summary to `sources/jinri-jiujia-wechat-links/2025-md-summary.json`

Important:

- `noProductDates` and `noCoreMaotaiDates` alone are not enough to prove a Markdown file is complete.
- Always audit table and row counts too.

## Generated outputs

### `sources/jinri-jiujia-wechat-links/2025-md/`

Formal Markdown snapshot directory.

Current audit at the time this note was written:

- Markdown files: 126
- Lowest table count in formal directory: 34
- Lowest row count in formal directory: 376
- Adapter mix: earlier files may show `generic` or `cdp-js-content`

### Temporary fastpath test output

Test output directory for `wechat_mp_fastpath.mjs`; this was removed after the validated captures were written to the formal `2025-md` directory.

Current files:

- `2025-09-22.md`
- `2025-09-23.md`

Both are test captures and should not be confused with the formal `2025-md` directory.

### `data-2025.json`

Core Moutai records extracted from Markdown snapshots.

### `all_prices-2025.jsonl`

All extracted price rows from Markdown snapshots.

### `sources/jinri-jiujia-wechat-links/2025-md-summary.json`

Machine-readable extraction summary.

Current summary at the time this note was written:

- `markdownFiles`: 126
- `coreRecords`: 126
- `allPriceRows`: 31884
- `missingMarkdownDates`: 88
- `noProductDates`: []
- `noCoreMaotaiDates`: []

### State / handoff files

- `2025-md-state.json`: state for earlier fetch scripts
- `2025-md-fastpath-state.json`: state for `wechat_mp_fastpath.mjs` when writing formal output
- temporary fastpath test state: removed after the formal output was validated
- `2025-md-handoff.md`: operational handoff notes from earlier work
- `WECHAT_FASTPATH.md`: how to use the defensive fast path

## Recommended continuation

Use `wechat_mp_fastpath.mjs`, not baoyu-fetch generic.

Example single-date continuation:

```powershell
node wechat_mp_fastpath.mjs `
  --cdp-url http://127.0.0.1:9223 `
  --links sources/jinri-jiujia-wechat-links/2025-links.json `
  --out-dir sources/jinri-jiujia-wechat-links/2025-md `
  --state sources/jinri-jiujia-wechat-links/2025-md-fastpath-state.json `
  --date 2025-09-22 `
  --force `
  --no-delay
```

Batch continuation:

```powershell
node wechat_mp_fastpath.mjs `
  --cdp-url http://127.0.0.1:9223 `
  --links sources/jinri-jiujia-wechat-links/2025-links.json `
  --out-dir sources/jinri-jiujia-wechat-links/2025-md `
  --state sources/jinri-jiujia-wechat-links/2025-md-fastpath-state.json `
  --max-fetch 8
```

After each batch:

```powershell
python scripts/2025-backfill/extract_2025_from_markdown.py
```

Also audit table counts:

```powershell
$rows = Get-ChildItem -LiteralPath '.\sources\jinri-jiujia-wechat-links\2025-md' -Filter '*.md' | ForEach-Object {
  $s = Get-Content -LiteralPath $_.FullName -Raw
  [pscustomobject]@{
    Date=$_.BaseName
    Tables=([regex]::Matches($s,'<table\b')).Count
    Rows=([regex]::Matches($s,'<tr\b')).Count
    Bytes=[Text.Encoding]::UTF8.GetByteCount($s)
    Adapter=([regex]::Match($s,'adapter:\s*"?([^"\r\n]+)"?')).Groups[1].Value
  }
}
$rows | Sort-Object Tables,Rows | Select-Object -First 20 | Format-Table -AutoSize
```

Any newly captured file with fewer than 30 tables or fewer than 300 rows should be treated as incomplete and retried.
