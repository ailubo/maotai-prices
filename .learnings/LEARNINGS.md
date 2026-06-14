# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260614-001] correction

**Logged**: 2026-06-14T14:54:00+08:00
**Priority**: critical
**Status**: resolved
**Area**: config

### Summary
全品类HTML table解析必须用td级解析，span级解析会因不同column count的表结构产生大量零值错误

### Details
今日酒价文章中的table有两种变体：
- 标准4列: 品名 | 规格 | 昨日行情 | 今日行情 → 取cells[2]和cells[3]为yesterday/today
- 特殊3列: 品名 | 规格 | 行情 → 只有单价格，取cells[2]为today, yesterday=null
- 3列表格出现在: 年份酒、生肖酒、老酒子分区

第一版解析器使用`re.findall(r'<span leaf="">([^<]*)</span>', row)`提取所有span，导致：
- 3列表格被误当4列解析 → cells[3]不存在 → today=0 (29条)
- 多行规格(如"46+70度/500ml")的第二个span被误当价格

### Suggested Action
解析流程: 按<tr>分组 → 按<td>分组 → 每个td内合并所有<span> → 按td数量判断3列/4列

### Metadata
- Source: user_feedback
- Related Files: batch_extract_all.mjs, all_prices.jsonl
- Tags: html-parsing, table-extraction, wechat-article

---

## [LRN-20260614-002] knowledge_gap

**Logged**: 2026-06-14T14:54:00+08:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
HTML &nbsp;实体在正则提取后不会被自动解码，必须显式过滤

### Details
笙乐飞天价格"2300&nbsp;"在markdown中存储为HTML实体`&nbsp;`，正则提取后得到字符串`"2300&nbsp;"`。
`int("2300&nbsp;")` → ValueError → 条目被跳过。
`re.sub(r'\u00a0', ...)`无法匹配，因为`&nbsp;`是6字符HTML实体，非Unicode字符U+00A0。

### Suggested Action
清洗步骤: `re.sub(r'&nbsp;|\u00a0|[⬆⬇➡]', '', combined).strip()`

### Metadata
- Source: error
- Related Files: batch_extract_all.mjs
- Tags: html-entity, parsing, edge-case

---

## [LRN-20260614-003] best_practice

**Logged**: 2026-06-14T14:54:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
发现问题后应立即修复而非只报告，即使已经commit/push也要追修

### Details
首次解析后发现29条零值错误和2条缺失。用户反馈"以后如果发现问题，要想办法解决问题，而不是躲过去"。
正确做法: 删除bad entries → 修复解析逻辑 → 重新append → regenerate → 再commit/push。

### Suggested Action
数据类任务: 解析后主动校验(today>0, 无missing known products) → 发现异常立即修复

### Metadata
- Source: user_feedback
- Tags: workflow, quality, self-correction

---
