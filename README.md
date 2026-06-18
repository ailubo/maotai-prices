# maotai-prices — 飞天茅台散瓶批价追踪

> AI agent 操作手册。2026 年 162 数据点 + 2025 年历史数据，来源今日酒价公众号。

## 文件结构

### 数据文件

| 文件 | 格式 | 用途 | 何时修改 |
|------|------|------|---------|
| `data.json` | JSON | 2026 茅台价格（162点），默认年份 | 每日追加 |
| `all_prices.jsonl` | JSONL | 2026 全品类酒价（251款×160天，31508行） | 每日追加 |
| `data-2021.json` | JSON | 2021 茅台价格（10点；OCR核心价） | 历史回填 |
| `all_prices-2021.jsonl` | JSONL | 2021 全品类酒价（1864行；OCR补入） | 历史回填 |
| `core_prices-2021-ocr.jsonl` | JSONL | 2021 OCR 核心飞天行（复核用） | 历史回填 |
| `all_prices-2021-ocr.jsonl` | JSONL | 2021 OCR 全品类行（复核用） | 历史回填 |
| `data-2022.json` | JSON | 2022 茅台价格（14点；10点OCR+4点HTML） | 历史回填 |
| `all_prices-2022.jsonl` | JSONL | 2022 全品类酒价（3614行；2384行OCR+1230行HTML） | 历史回填 |
| `core_prices-2022-ocr.jsonl` | JSONL | 2022 OCR 核心飞天行（复核用） | 历史回填 |
| `all_prices-2022-ocr.jsonl` | JSONL | 2022 OCR 全品类行（复核用） | 历史回填 |
| `data-2023.json` | JSON | 2023 茅台价格（12点） | 历史回填 |
| `all_prices-2023.jsonl` | JSONL | 2023 全品类酒价（3871行） | 历史回填 |
| `data-2024.json` | JSON | 2024 茅台价格（13点） | 历史回填 |
| `all_prices-2024.jsonl` | JSONL | 2024 全品类酒价（3718行） | 历史回填 |
| `data-2025.json` | JSON | 2025 茅台价格（189点） | 批量回填 |
| `all_prices-2025.jsonl` | JSONL | 2025 全品类酒价（47774行） | 批量回填 |
| `scripts/2025-backfill/state-2025.json` | JSON | 2025 回填断点续传状态 | 已归档 |
| `regenerate.py` | Python | 一键重生成所有 MD（data.json → 月报+总览） | 改 data.json 后必跑 |

### 生成文件（regenerate.py 自动产出）

| 文件 | 说明 |
|------|------|
| `2026/2026-{MM}.md` | 按月明细表 |
| `2026总览.md` | 年度全表 |

### 脚本

| 文件 | 用途 | 用法 |
|------|------|------|
| `batch_extract_all.mjs` | Light 模式批量提取 | `node batch_extract_all.mjs [--year YYYY] <links.json>` |
| `scripts/2025-backfill/` | 历史回填一次性工具 | 仅审计/重跑 2021-2025 存档时使用 |
| `archived/batch_extract_prices.mjs` | 旧版（仅茅台），已归档 | 不再使用 |

### 数据源

| 目录 | 说明 |
|------|------|
| `sources/jinri-jiujia-wechat-links/` | 今日酒价公众号链接采集 |
| `sources/jinri-jiujia-wechat-links/2025-links.csv` | 2025 年已验证链接（214篇） |

## 命名约定

```
当前年：  data.json, all_prices.jsonl, state.json
特定年：  data-YYYY.json, all_prices-YYYY.jsonl, state-YYYY.json
```

所有输出文件由 `--year` 参数自动推导，不需要手工指定文件名。

## 2025 数据频率

`今日酒价` 在 2025 年中切换发布频率：1-4 月基本每月 10 日一篇，6 月进入过渡期，7 月 4 日起转为逐日发布。因此 `data-2025.json` 上半年只有月度颗粒度是源头限制，不是抓取漏项；真正接近日频的数据从 2025-07 开始。链接错指 2026 文章的记录见 `sources/jinri-jiujia-wechat-links/2025-wrong-links.md`。

## 2021-2024 历史回填

2021-2024 已使用 `wechat_mp_fastpath.mjs` 存档到 `sources/jinri-jiujia-wechat-links/YYYY-md/`。2021 全年和 2022-01 至 2022-10 的旧文章是图片型正文，没有 HTML 表格；核心飞天散瓶/原箱价通过 Windows OCR 从长图补入 `data-2021.json` / `data-2022.json`，全品类 OCR 行已补入 `all_prices-2021.jsonl` / `all_prices-2022.jsonl`，OCR 中间文件在 `sources/jinri-jiujia-wechat-links/YYYY-ocr/`。2022-11 起、2023、2024 为 HTML 表格，可抽取到 `data-YYYY.json` 和 `all_prices-YYYY.jsonl`。当前仓库没有 `2020-links.json/csv`。

## 更新流程

### 日常更新（自动化，每天 14:00）

**优先源**：用户提供今日酒价公众号文章链接 → baoyu-fetch 直抓
```bash
bun cli.ts "https://mp.weixin.qq.com/s/xxx" --output result.md
# 从 markdown 提取 26年飞天(散)/(原) 价格
```

**兜底搜索**：`WebSearch "今日酒价 飞天茅台散瓶"` + `site:cls.cn "飞天茅台" "批价"`

### 批量回填（按需，light 模式）

```bash
# 当前年（2026）
node batch_extract_all.mjs sources/.../2026-links.json

# 历史年份
node batch_extract_all.mjs --year 2025 sources/.../2025-links.json

# 输出自动命名：data-2025.json + all_prices-2025.jsonl
```

### 善后

```bash
python regenerate.py
git add -A && git commit -m "更新: YYYY-MM-DD" && git push origin main
```

## 信号规则

🔴 = 散瓶 < 当期指导价 | 🟡 = 指导价~1800 | 🟢 = >1800

指导价：1499 (2026/1/1~3/30) → 1539 (2026/3/31起)

## 注意事项

- **改 data.json 后必须跑 `python regenerate.py`**
- **`batch_extract_all.mjs` 需要 `puppeteer-core`**（`bun install`）
- **Chrome 路径**：默认 `C:/Program Files/Google/Chrome/Application/chrome.exe`，可通过 `CHROME_PATH` 环境变量覆盖
- **Chrome Profile**：默认 `C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile`
- **state 文件**：自动创建，用于断点续传，不要手动删除（除非想重新全量抓取）
