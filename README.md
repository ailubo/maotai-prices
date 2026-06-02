# maotai-prices — 飞天茅台散瓶批价追踪

> 如果你是 Claude Code，读完后按更新流程操作。本文件是 agent 操作手册，不是人类展示页。

## 文件结构

| 文件 | 用途 | 何时修改 |
|------|------|---------|
| `data.json` | 唯一数据源（逐日记录） | 每次追加新数据 |
| `regenerate.py` | 一键重生成所有 MD | 改 data.json 后必跑 |
| `2026/2026-{MM}.md` | 按月明细表 | regenerate.py 自动生成 |
| `2026总览.md` | 年度全表 | regenerate.py 自动生成 |
| `README.md` | 本文件 | 结构变化时 |

## data.json 字段

```
{
  "date": "2026-01-01",          // YYYY-MM-DD
  "sanping": 1490,               // 散瓶批价，无数据填 null
  "yuanxiang": 1660,             // 原箱批价，无数据填 null
  "guide_price": 1499,           // 由 regenerate 自动填
  "signal": "🔴",                // 由 regenerate 自动算
  "source": "财联社",            // 数据来源
  "note": "备注"                 // 可选
}
```

## 更新流程（AI agent 执行步骤）

### 1. 搜索

WebSearch 关键词：
- `"今日酒价披露" "飞天茅台散瓶" 2026`（财联社引用，最可靠）
- `site:cls.cn "飞天茅台" "批价" 2026`
- `winesinfo.net "飞天(散)"`
- `云酒网 yunjiu.com 飞天茅台 批价`
- `huangjinjiage.cn 飞天茅台`

### 2. 对比去重

读 data.json → 取 `prices[].date` 集合 → 新数据跳过已有日期

### 3. 追加

新条目只填 `date` + `sanping` + `yuanxiang` + `source` + `note`，**不填 guide_price 和 signal**（由 regenerate 算）

### 4. 重生成

```bash
cd c:/Users/PC/WorkBuddy/Claw/maotai-prices
python regenerate.py
```

### 5. 推送

```bash
git add -A
git commit -m "更新: 2026-06-02 新增3个数据点"
git push origin master:main
```

无新数据：`git commit -m "无新增数据"` 后仍然 push（保持仓库活跃）

## 信号规则

| 信号 | 条件 | 含义 |
|:--:|------|------|
| 🔴 | 散瓶 < 当期指导价 | 渠道亏损 |
| 🟡 | 指导价 ~ 1800 | 正常区间 |
| 🟢 | > 1800 | 溢价区间 |

> 指导价历史：¥1,499 (1/1~3/30) → ¥1,539 (3/31起)

## 推送注意事项

- **代理必须 TUN/虚拟网卡模式**：SOCKS/HTTP 代理(7897)会导致 git TLS 握手失败
- remote URL 需含 token：`https://ailubo:TOKEN@github.com/ailubo/maotai-prices.git`
- git push 失败时用 `gh api` 备选路径（blob → tree → commit → ref update）
- 分支：本地 `master` → 远程 `main`

## 数据源可靠性分级

| 级别 | 来源 | 说明 |
|:--:|------|------|
| ⭐⭐⭐ | 财联社(cls.cn)引用今日酒价 | 散瓶+原箱配对，行业标杆 |
| ⭐⭐ | 云酒网、金价查询网、winesinfo.net | 单日数据，URL不稳定 |
| ⭐ | 界面新闻/易茅时价、雪球、什么值得买 | 转载/社区，需交叉验证 |
| ❌ | meijiu.com、maotai.wgnds.com | 不可达 |
| ⚠️ | jujindata.com | 可访问但数据是复合指数(1660/1670)，非批价 |
