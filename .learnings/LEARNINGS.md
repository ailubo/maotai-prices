# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260619-002] best_practice

**Logged**: 2026-06-19T00:00:00+08:00
**Priority**: high
**Status**: active
**Area**: git-workflow

### Summary
Long-running data collection should be committed and pushed at meaningful checkpoints, not only at the end.

### Details
For WeChat/manual data collection, the user expects checkpoint pushes without repeated reminders. Useful checkpoints include: finishing one year, recovering a verified batch of links, fixing a known wrong-link date, or writing a durable learning/rule. This reduces risk from UI state loss, conversation interruption, local workspace drift, or forgotten file updates.

### Suggested Action
When a task produces durable files and a coherent unit is verified, run `git status`, review the diff, commit with the affected date/range in the message, push to `origin/main`, and confirm the commit hash. Do this proactively for multi-stage tasks.

### Metadata
- Source: user_feedback
- Tags: git, checkpoint, push, long-running-task, data-quality

---

## [LRN-20260619-001] best_practice

**Logged**: 2026-06-19T00:00:00+08:00
**Priority**: high
**Status**: active
**Area**: data-collection

### Summary
WeChat official-account collection must be screenshot-led, account-scoped, and date-validated before writing links.

### Details
During the Jinri Jiujia WeChat link recovery task, the biggest operational failure was acting from remembered coordinates instead of first inspecting the current screenshot. The search icon, account header, result title, account avatar/name area, browser tabs, and article menu all occupy nearby but different hit zones. A wrong click can switch pages, open the account profile, minimize the window, or leave the search-result context without immediately looking broken.

The reliable workflow is:
- Capture and inspect the current WeChat window screenshot before each new UI phase.
- For official-account search, click the magnifying-glass icon inside the account page, not global WeChat search or the top-level "Article" search tab.
- Search with the exact target date plus keyword, for example `2025年5月10日 批发参考价`.
- Use only the `今日酒价 发表的文章` result group. Ignore global article results and sticker/image groups.
- Click the article title text inside the result card, not the account avatar/name area and not surrounding whitespace.
- After opening a candidate, copy the article URL from the article menu and validate `mp.weixin.qq.com` HTML `ct`/publish time against the target date before updating CSV/JSON.
- If the visible search-result snippet already shows another year/date, do not accept it without opening and validating; usually it is a false positive from a later-year article.

### Suggested Action
For future WeChat desktop UI work, use a checkpoint loop: screenshot -> identify exact hit target -> click once -> screenshot verify -> proceed. Never chain coordinate guesses across screens, and never write a link until the article publish date equals the requested date.

### Metadata
- Source: user_feedback
- Related Files: sources/jinri-jiujia-wechat-links/2025-links.csv, sources/jinri-jiujia-wechat-links/2025-wrong-links.md
- Tags: wechat-ui, official-account-search, date-validation, data-quality

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

## [LRN-20260619-003] correction

**Logged**: 2026-06-19T13:55:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
agent-browser eval 不支持裸 `return` 语句，必须用 IIFE 包裹

### Details
`agent-browser eval "const x = 1; return x;"` → `SyntaxError: Illegal return statement`
正确写法: `agent-browser eval "(function(){ const x = 1; return x; })()"`
另外 `agent-browser eval` 的代码内部访问 DOM 元素的 `.href` 属性前需判空（`linkEl ? linkEl.href : ''`），否则 `TypeError: Cannot read properties of null`。

### Suggested Action
所有 agent-browser eval 命令统一用 `(function(){ ... })()` 包裹。

### Metadata
- Source: error
- Tags: agent-browser, eval, iife, javascript

---

## [LRN-20260619-004] correction

**Logged**: 2026-06-19T13:55:00+08:00
**Priority**: low
**Status**: pending
**Area**: config

### Summary
微信专辑页"倒序"按钮需点击 span.album-sort__word 直接元素，parentElement.click() 不生效

### Details
此前任务中使用 `el.parentElement.click()` 点击包含"倒序"文本的父元素，但实际未触发排序。
改用 `document.createTreeWalker` 找到文本节点，取其 `parentElement`（即 span.album-sort__word），直接 `.click()` 才生效。

### Suggested Action
自动化脚本中倒序点击改为: find text node "倒序" → node.parentElement.click()

### Metadata
- Source: error
- Tags: wechat, album-page, ui-interaction, agent-browser

---


**Logged**: 2026-06-18T13:56:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
maotai-prices 项目本地分支为 `main`，git push 必须用 `main:main` 而非 `master:main`

### Details
自动化任务脚本中默认写 `git push origin master:main`，但本项目的本地分支名实际为 `main`。
错误: `error: src refspec master does not match any`
修正: `git push origin main:main`

此错误在 6/16 和 6/18 均出现过，属于重复模式。

### Suggested Action
自动化任务中的 git push 命令统一使用 `main:main` 或 `git push origin HEAD:main`。

### Metadata
- Source: error
- Tags: git, push, branch-name
- Recurrence-Count: 2

---
