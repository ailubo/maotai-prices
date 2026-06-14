# maotai-prices — 飞天茅台散瓶批价追踪

> AI agent 操作手册。131 数据点，来源今日酒价公众号。

## 文件结构

| 文件 | 用途 | 何时修改 |
|------|------|---------|
| `data.json` | 茅台散瓶/原箱数据源（131点） | 每次追加 |
| `all_prices.jsonl` | 全品类酒价（2.4万行，251款×110天） | 批量回填或每日追加 |
| `regenerate.py` | 一键重生成所有 MD | 改 data.json 后必跑 |
| `batch_extract_all.mjs` | light模式批量提取脚本 | 不需日常改 |
| `2026/2026-{MM}.md` | 按月明细表 | regenerate.py 自动生成 |
| `2026总览.md` | 年度全表 | regenerate.py 自动生成 |

## 更新流程

### 日常更新（自动化，每天 14:00）

**优先源**：用户提供今日酒价公众号文章链接 → baoyu-fetch 直抓
```bash
bun cli.ts "https://mp.weixin.qq.com/s/xxx" --output result.md
# 从 markdown 提取 26年飞天(散)/(原) 价格
```

**兜底搜索**：`WebSearch "今日酒价 飞天茅台散瓶" ` + `site:cls.cn "飞天茅台" "批价"`

### 批量回填（按需，light 模式）

```bash
# 1. 用 agent-browser 提取专辑页全部链接
agent-browser open "https://mp.weixin.qq.com/mp/appmsgalbum?..."
agent-browser eval "..." # 提取 data-link
# 2. light模式批量提取
cd xhs-bulk-download-project
node batch_extract_all.mjs <links.json> <data.json>
# 输出: data.json（茅台）+ all_prices.jsonl（全品类）
```

### 善后

```bash
python regenerate.py
git add -A && git commit -m "更新: YYYY-MM-DD" && git push origin main
```
