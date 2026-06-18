# 2025 今日酒价 Markdown 抓取交接

更新时间：2026-06-17 晚

## 当前进度

- 目标链接来源：`sources/jinri-jiujia-wechat-links/2025-links.json` / `2025-links.csv`
- Markdown 保存目录：`sources/jinri-jiujia-wechat-links/2025-md/`
- 已成功保存 Markdown：99 篇
- 当前失败记录：0
- 已抽取茅台核心记录：99 条
- 已抽取全品类价格：25040 行
- 剩余未抓 Markdown：115 篇
- 下一篇应从：`2025-09-23`

当前输出文件：

- `data-2025.json`
- `all_prices-2025.jsonl`
- `sources/jinri-jiujia-wechat-links/2025-md-summary.json`
- `sources/jinri-jiujia-wechat-links/2025-md-state.json`

## 已新增脚本

- `scripts/2025-backfill/fetch_2025_markdown.mjs`
  - 使用 baoyu-fetch CLI 抓取微信文章为 Markdown。
  - 默认节奏：每篇随机 5-10 秒，每批 8 篇，批间休息 60 秒。
  - 支持断点续跑；已有合格 Markdown 会自动跳过。
  - 支持 `BAOYU_CDP_URL`，可复用一个直连 Chrome。
- `scripts/2025-backfill/extract_2025_from_markdown.py`
  - 从已保存的 Markdown HTML table 中抽取茅台核心价格和全品类价格。
  - 输出 `data-2025.json` 和 `all_prices-2025.jsonl`。

## 重要注意事项

- 用户希望国内微信页面不要走代理。系统 WinINET 代理曾显示为 `127.0.0.1:7897`，Chrome 默认会吃系统代理。
- 不要改用户系统全局代理。可单独启动一个直连 Chrome：

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

然后抓取时使用：

```powershell
$env:BAOYU_CDP_URL="http://127.0.0.1:9223"
node scripts/2025-backfill/fetch_2025_markdown.mjs --max-fetch 8
Remove-Item Env:\BAOYU_CDP_URL -ErrorAction SilentlyContinue
```

如果个别日期超时但未生成文件，可放宽超时单篇补：

```powershell
$env:BAOYU_CDP_URL="http://127.0.0.1:9223"
$env:BAOYU_FETCH_TIMEOUT_MS="240000"
$env:BAOYU_PAGE_TIMEOUT_MS="60000"
node scripts/2025-backfill/fetch_2025_markdown.mjs --max-fetch 1
Remove-Item Env:\BAOYU_CDP_URL -ErrorAction SilentlyContinue
Remove-Item Env:\BAOYU_FETCH_TIMEOUT_MS -ErrorAction SilentlyContinue
Remove-Item Env:\BAOYU_PAGE_TIMEOUT_MS -ErrorAction SilentlyContinue
```

## 最近发生过的问题

- `2025-10-12` 曾触发微信“环境异常/去验证”，用户打开 Chrome 后可以看到公众号正文，后续已补成功。
- `2025-10-10`、`2025-10-12`、`2025-10-03`、`2025-10-02`、`2025-10-01`、`2025-09-30`、`2025-09-28`、`2025-09-25` 曾出现超时，放宽超时后均已补成功。
- 当前失败列表为空。

## 接续建议

1. 新对话先读本文件和 `sources/jinri-jiujia-wechat-links/README.md`。
2. 确认状态：

```powershell
python scripts/2025-backfill/extract_2025_from_markdown.py
```

3. 从 `2025-09-23` 开始继续。
4. 先继续使用 `scripts/2025-backfill/fetch_2025_markdown.mjs --max-fetch 8`，每批后跑 `scripts/2025-backfill/extract_2025_from_markdown.py` 检查：
   - `noProductDates` 应为空。
   - `noCoreMaotaiDates` 应为空。
   - `state.failed` 应为空。
5. 如果继续觉得 baoyu CLI 太慢，可再实现“单 Chrome/CDP 会话批量导航 + 保存 `#js_content` 为 Markdown”的轻量脚本，但不要在没有小样本验证前替换当前产物。
