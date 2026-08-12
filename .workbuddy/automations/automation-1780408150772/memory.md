# 每日茅台批价更新 - 执行记忆

## 最近执行: 2026-08-12 15:05 (通知通道核查)

### ⚠️ 关键发现
- **agentmail 邮箱未开通**（GetMe 返回 status=not_bound）：connector 显示 connected 但服务端未绑定
- 两个自动化已配 connectorIds=["agent-mail"] 且提示词含告警邮件逻辑，**但邮件目前发不出去**
- **待用户开通**: 客户端「上方开通面板」或「更多-我的邮箱」完成 agentmail 开通后，告警邮件通道才真正可用
- 开通后可查看位置: WorkBuddy 客户端 agentmail 收件箱（「更多-我的邮箱」入口）
- 若用户不打算开通 agentmail，需移除自动化中的告警邮件逻辑或改走其他通道（如飞书桥）

## 上次执行: 2026-08-12 15:02 (通知通道配置)

### 结果
- ✅ **通知通道落地**: 两个自动化(14:00首检 + 20:30补检)均接入 agentmail 邮箱连接器
  - ⚠️ 平台推送开关 push_to_wechat/push_to_wecom_bot 经实测**工具不落盘**(update 返回成功但 DB 恒为 0)，不可依赖
  - 替代方案: connectorIds=["agent-mail"] 实测可写入 ✅ → 失败类状态自动发告警邮件
  - 提示词已加"失败告警邮件"段落: 失败类 STATUS / GAPS / 20:30仍未发布 → agentmail 发邮件；正常状态不发
- 收件人: 用户本人邮箱（自动化 agent 执行时用 GetMe 解析）

## 上次执行: 2026-08-12 14:48 (codex 审查 + 全面加固)

### 结果
- ✅ **Codex 只读审查完成**（8m18s, gpt-5.6-sol）：指出 5 P0 + 8 P1 + 2 P2，核心= "数据已恢复但防静默失败门禁未建立"
- ✅ **P0/P1 修复已落地并推送**（0963dc6）：
  1. `scripts/daily_update.sh` — 确定性状态机 runner（SUCCESS/VERIFIED_NOT_PUBLISHED/STALE_NO_PUBLISH/DISCOVERY_FAILED/FETCH_FAILED/PARSE_FAILED/COMMIT_FAILED/PUSH_FAILED/ALREADY_EXISTS），含 CDP about:blank 探测、精确 git add、SHA 验证
  2. 三个 Playwright 脚本 — 倒序失败必抛错（不再假成功）、process.exitCode 替代 try/catch 内 exit（finally 必执行）、锁带 PID 陈旧检测、URL host 校验、排序真伪校验
  3. `parse_daily.py` — 硬校验（正文日期精确匹配、核心价 1000~6000、产品数≥50、核心产品必在）+ 原子写入（临时文件+os.replace）
  4. `scripts/verify_data.py` — 日历 vs data.json vs jsonl 三向缺口检测（停更例外读 sources/停更例外.md）
  5. `sources/停更例外.md` — 5 天停更清单（1/11、2/16-19）
  6. README 全面更新
- ✅ **自动化配置更新**：14:00 任务提示词改为状态机分支；新增 20:30 晚间补检任务（automation-1786517311073，因 Claw 工作区限制 cwds 为系统分配目录，prompt 内绝对路径 cd 覆盖）
- ✅ 数据完整性: verify_data.py --quiet → OK (219 点, 无缺口, 5 例外)
- ⚠️ 已知残留(非本次范围): all_prices.jsonl 三种历史格式并存、31 处跨文件来源冲突（均为非今日酒价来源日期）、README 统计改为运行 verify 取数

### 事故根因（codex 确认）
- agent-browser "命令成功"≠"页面可读"（CDP about:blank）；"未发布"与"无法观测"未分状态；无独立缺口探针；无晚间补偿

---
## 上次执行: 2026-08-12 14:26 (三次执行，全量缺口核验+补录)

### 结果
- ✅ **全量核验**: 用 Playwright 滚动加载拉取专辑全部 218 篇文章，逐日比对 data.json
- ✅ **补录 6 天**: 6/29(1650/1630), 7/14(1655/1635), 7/16(1650/1630), 7/17(1650/1630), 7/18(1700/1675), 7/19(1720/1680)
  - 7/18 价格跳涨(散1630→1675)正是 i茅台年内第二次调价日(1639)，符合逻辑
  - all_prices.jsonl +1044条 (6天×174)
- ❌ **5 天无法补**: 1/11(周日), 2/16-19(春节) — 全量 218 篇中无文章，公众号停更，非漏抓
- ✅ data.json: 219 数据点 (4🔴 213🟡 0🟢)，2026-06.md 30行、2026-07.md 31行(7月全)
- ✅ git push: 8a40ddf
- ✅ 新增 scripts/fetch_article_playwright.cjs (单篇文章 Playwright 直抓，7/16 反爬时 baoyu-fetch 失败的兜底)

### 全量拉取方法
- scripts/fetch_recent_articles.cjs 已增强滚动加载(30轮×1.5s)，可拉全部 218 篇
- 用法: node fetch_recent_articles.cjs 220 > /tmp/all.json

## 二次执行: 2026-08-12 14:20 (修复后补录成功)

### 结果
- ✅ **重大修复**: agent-browser CDP 故障(about:blank)已绕开，改用 Playwright 方案
  - 根因确认: agent-browser open 报成功但页面停在 about:blank，eval/snapshot 全失效（非 WeChat DOM 变化）
  - 新脚本: scripts/fetch_latest_playwright.cjs (Playwright + baoyu-skills Chrome profile + 代理)
  - 主脚本 fetch_latest_wechat_album_item.sh 已改写为调用 Playwright 方案，实测可用
- ✅ **补录成功**: 8/10、8/11 数据补齐 + 8/12 新增
  - 8/10: 散=1710, 原=1730 (持平8/9)
  - 8/11: 散=1710, 原=1720 (原箱跌10)
  - 8/12: 散=1705⬇5, 原=1720 (散瓶跌5) 🟡
  - all_prices.jsonl 追加 3天×175条=525条
  - regenerate.py 成功: 213数据点 (4🔴 207🟡 0🟢)
- ✅ git push: 0712286 (数据) + 149bee5 (修复脚本)
- ✅ 浏览器会话清理成功(无活跃会话)

### 经验
- Playwright 可用: NODE_PATH=node/workspace/node_modules, 用系统 Chrome (executablePath)
- 抓多篇: scripts/fetch_recent_articles.cjs <N> (倒序取最近N篇)
- 文章为 HTML table 格式，parse_daily.py 的 td级解析可复用；品牌头在每表首行
- 备用: fetch_recent_articles.cjs 可一次拉最近8篇标题+链接

---
## 首次执行: 2026-08-12 13:55

### 结果
- ⏭️ 跳过: 8/12 今日酒价公众号文章尚未发布(14:00前)，按规则跳过数据写入
- ❌ agent-browser 脚本持续失败: "找不到倒序按钮"（第4天，实为 CDP about:blank 故障）
- ⚠️ 163.com 镜像 8/10、8/11 两篇均已发布（L3VDEC4L、L41VVON9），但均为纯图片(走势曲线图)，无文本表格，无法直接提取批价
- ✅ 浏览器会话清理成功(maotai-daily 已关闭，无活跃会话)

### 第三方行情快照
- 8/10 批价(中国商报引用今日酒价): 散瓶=1710, 原箱=1730（持平8/9）
- 8/11 批价(恒信名酒行): 散瓶=1710, 原箱=1730（持平8/10）
- 8/11 批价(易茅时价/mffb.com.cn): 散瓶=1720, 原箱=1730
- 8/11 批价(中国商报): 回落到1720（未注明散/原）
- 8/12 终端零售(酒价内参): 飞天=1789(+8), 精品=2454(+22)

### 数据缺口 (已补录，无缺口)
- ~~8/10~~ ✅ 已补: 散=1710, 原=1730
- ~~8/11~~ ✅ 已补: 散=1710, 原=1720
- ~~8/12~~ ✅ 已收: 散=1705, 原=1720

### 待解决
- ✅ 已修复: agent-browser CDP 故障已绕开（Playwright 方案），连续4天问题终结
- 后续: 观察 Playwright 方案在多日运行中的稳定性；163.com 镜像自8/10起为纯图表格式，已不可作 fallback

---
## 上次执行: 2026-08-11 13:55

### 结果
- ⏭️ 跳过: 8/11 今日酒价公众号文章尚未发布(通常晚上7-8点发布)，按规则跳过数据写入
- 🔴 agent-browser CDP 异常持续: fetch_latest_wechat_album_item.sh 执行失败("找不到倒序按钮")，与昨日相同
- ✅ 浏览器会话清理成功(maotai-daily 已关闭，无活跃会话)

### 行情背景
- 最新收录数据仍为 8/9: 散瓶=1710, 原箱=1730
- 8/10 今日酒价数据(据中国商报引用): 散瓶=1710, 原箱=1730(持平8/9，无变动)
- 8/11 终端零售: 飞天1781(+4), 精品2432(+10)——酒价内参数据(新浪财经)
- 8/8 茅台自营店提价至1753元/瓶(半月内第二次)，与i茅台1639形成双轨制

### 待解决
- ⚠️ agent-browser CDP 问题需排障，已连续两天无法正常获取专辑页
- 备用方案可用: baoyu-fetch (限前20条正序)、163.com 镜像、WebSearch 第三方引用

---

## 上次执行: 2026-08-10 13:55

### 结果
- ⚠️ 部分完成: 8/9(今日酒价, 散瓶=1710⬆15, 原箱=1730⬆20) 已更新
- ❌ 8/10: 今日酒价公众号文章尚未发布（通常晚上7-8点发布），按规则跳过
- ✅ all_prices.jsonl 追加 195 条全品类数据(8/9)
- ✅ 8/9 数据来源: 163.com 白酒经销商学院镜像(https://www.163.com/dy/article/L3SNI1CK0514CPVK.html)
- ✅ git push 成功 (main:main, 931cf46)

### 异常情况
- 🔴 **agent-browser 严重异常**（本会话首次出现）
  - `agent-browser open` 报"成功"，但页面状态一直是 about:blank
  - 即使 example.com 也复现：`get url` 返回 about:blank
  - WeChat 公众号页 console 仍能正常加载(显示analytics), 但 eval/snapshot/get 都返回 about:blank
  - `tab list` 始终显示 about:blank 单tab
  - 切换 --session/--headed/--user-data-dir/--init-script 均无效
- 备用方案: baoyu-fetch 部分可用(只能拿第一页20条，按时间正序)，但无法倒序拉最新
- 最终 fallback: WebSearch 找到 163.com 镜像的今日酒价 8/9 完整33款名酒批价表

### 8/9 关键变动
- 飞天散瓶涨15(1695→1710), 原箱涨20(1710→1730)
- 25年飞天(原)涨20(1780→1800), 25年飞天(散)涨20(1730→1750)
- 佰草香涨30(450→480)
- 其他全部持平

### 8/10 行情背景
- 茅台自营店8/8零售价涨至1753元(i茅台仍1639元, 价差114元)
- 8/10 终端零售价：飞天涨4元至1777元, 精品涨12元至2422元(创近月新高)
- 自营店茅台精品同步涨价至2410元, 马年生肖1951元

### 后续建议
- Agent-browser CDP 连接问题需要排错（可能今天修了 Chrome 或环境变化）
- 备用方案优化: 增加 mffb.com.cn / 163.com 镜像作为 fallback
- 8/10 今晚7-8点观察公众号文章是否发布

---

## 上次执行: 2026-08-09 13:55
- 跳过: 文章未发布

### 关键变动
- 飞天散瓶跌5(1700→1695), 原箱跌5(1715→1710), 25年飞天(散)跌10(1740→1730)
- 公斤茅台持平(3250), 十五年持平(4130), 精品持平(2340)

---

## 2026-08-08 13:55
- ✅ 新增数据: 8/8(今日酒价, 散瓶=1695⬇5, 原箱=1710⬇5) 均微降
- ✅ 信号🟡, 最新: 散瓶=1695 原箱=1710 价差15元
- ✅ all_prices.jsonl 追加 176 条全品类数据
- ✅ regenerate.py 成功, 209数据点 (4🔴 203🟡 0🟢)
- ✅ git push 成功 (main:main, 52da40b)
- ✅ agent-browser + baoyu-fetch 全流程正常
