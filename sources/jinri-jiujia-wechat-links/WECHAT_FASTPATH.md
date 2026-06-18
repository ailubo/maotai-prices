# WeChat article fast path handoff

This project has a standalone extractor for WeChat Official Account article pages:

```powershell
node wechat_mp_fastpath.mjs --help
```

The script is intentionally independent from `baoyu-fetch`. It connects to an existing Chrome DevTools Protocol endpoint, opens each `mp.weixin.qq.com` URL, reads the WeChat DOM directly, and saves `#js_content` as Markdown with embedded HTML tables and remote image links.

## Why this exists

`baoyu-fetch` generic adapter is not a good fit for these pages:

- It uses the generic webpage pipeline rather than a WeChat-specific DOM path.
- It waits for navigation/network idle and scrolls the page before extraction.
- Markdown output can trigger remote `defuddle.md` fallback.
- Some CDP/fetch operations do not have command-level timeouts.

For the "今日酒价" price-table articles, the reliable source is already in the page:

- title: `#activity-name`
- account name: `#js_name`
- publish time: `#publish_time`
- content: `#js_content`
- images: `img[data-src]` should stay as remote URLs

## Start a direct Chrome

Use a dedicated Chrome with no proxy for domestic WeChat pages:

```powershell
$chrome="C:\Program Files\Google\Chrome\Application\chrome.exe"
$profile="C:\Users\PC\AppData\Roaming\baoyu-skills\chrome-profile-direct"
Start-Process -FilePath $chrome -ArgumentList @(
  "--remote-debugging-port=9223",
  "--user-data-dir=$profile",
  "--no-proxy-server",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-background-networking",
  "--disable-sync",
  "--remote-allow-origins=*",
  "about:blank"
)
```

Do not change the user's global proxy settings.

## Run for 2025 links

Small batch, matching the user's requested rhythm:

```powershell
node wechat_mp_fastpath.mjs `
  --cdp-url http://127.0.0.1:9223 `
  --links sources/jinri-jiujia-wechat-links/2025-links.json `
  --out-dir sources/jinri-jiujia-wechat-links/2025-md `
  --max-fetch 8
```

Defaults:

- delay between articles: 5-10 seconds
- batch size: 8 fetched attempts
- batch rest: 60 seconds
- account check: `今日酒价`
- publish-date check: enabled when the record has a `date`
- completeness check: at least 30 tables and 300 table rows
- stability check: table count, row count, and text length must stay unchanged for 3 consecutive polls before saving

These quality gates are important. Earlier CDP experiments produced partial pages with only 4-19 tables while a normal complete "今日酒价" price article has about 34-35 tables. Do not accept low-table markdown just because `scripts/2025-backfill/extract_2025_from_markdown.py` still finds Moutai rows.

Older 2021 and early 2022 articles can be image-based, with zero HTML tables but complete remote image links inside `#js_content`. For those archive-only pages, use `--allow-no-table --min-tables 0 --min-rows 0`, then rely on the extraction summary to show `noProductDates`.

For image-based pages, OCR the long price-table images and merge the recovered core Moutai records:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/2025-backfill/ocr_wechat_images.ps1 -Year 2022 -Date 2022-10-10 -IncludeUnknownHeightPng
python scripts/2025-backfill/extract_ocr_core.py --year 2022
python scripts/2025-backfill/merge_ocr_core.py --year 2022
```

Single date retry:

```powershell
node wechat_mp_fastpath.mjs `
  --cdp-url http://127.0.0.1:9223 `
  --links sources/jinri-jiujia-wechat-links/2025-links.json `
  --out-dir sources/jinri-jiujia-wechat-links/2025-md `
  --date 2025-09-23 `
  --force
```

Single URL:

```powershell
node wechat_mp_fastpath.mjs `
  --cdp-url http://127.0.0.1:9223 `
  --url "https://mp.weixin.qq.com/s/..." `
  --date 2025-09-23 `
  --out-dir sources/jinri-jiujia-wechat-links/2025-md
```

## Outputs

Markdown files are saved as:

```text
sources/jinri-jiujia-wechat-links/2025-md/YYYY-MM-DD.md
```

The front matter includes:

- `title`
- `url`
- `requestedUrl`
- `accountName`
- `publishTime`
- `publishDate`
- `coverImage`
- `adapter: "wechat-mp-fastpath"`
- `tableCount`
- `rowCount`
- `imageCount`

The state file defaults to:

```text
sources/jinri-jiujia-wechat-links/2025-md-fastpath-state.json
```

## After fetching

Run the existing parser:

```powershell
python scripts/2025-backfill/extract_2025_from_markdown.py --year 2025
```

Expected parser outputs:

- `data-2025.json`
- `all_prices-2025.jsonl`
- `sources/jinri-jiujia-wechat-links/2025-md-summary.json`

Watch these summary fields:

- `noProductDates` should stay empty
- `noCoreMaotaiDates` should stay empty
- fast path state `failed` should stay empty or be manually reviewed

Also audit table counts after every batch:

```powershell
$rows = Get-ChildItem -LiteralPath '.\sources\jinri-jiujia-wechat-links\2025-md' -Filter '*.md' | ForEach-Object {
  $s = Get-Content -LiteralPath $_.FullName -Raw
  [pscustomobject]@{
    Date=$_.BaseName
    Tables=([regex]::Matches($s,'<table\b')).Count
    Rows=([regex]::Matches($s,'<tr\b')).Count
    Bytes=[Text.Encoding]::UTF8.GetByteCount($s)
  }
}
$rows | Sort-Object Tables,Rows | Select-Object -First 20 | Format-Table -AutoSize
```

Any newly fetched article below 30 tables or 300 rows should be treated as incomplete and re-fetched with `--force`.

## Safety rules

- Do not use WeChat global search results for link collection.
- Do not mix other Official Accounts into the link file.
- Do not download images; keep remote `mmbiz.qpic.cn` / WeChat image URLs.
- Do not route these domestic pages through the user's proxy.
- Do not use `baoyu-fetch` generic adapter for this batch unless explicitly debugging it.
