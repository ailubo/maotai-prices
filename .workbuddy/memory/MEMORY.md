# maotai-prices 项目长期记忆

## 全品类解析规范
- **td级解析**：按`<td>`分组而非`<span>`，先合并每个td内所有span
- **列数识别**：标准表4列(品名/规格/昨日/今日)，年份酒/生肖/老酒3列(品名/规格/行情)
- **清洗规则**：`re.sub(r'&nbsp;|\u00a0|[⬆⬇➡]', '', text).strip()`
- **校验**：解析后检查 today>0 和已知product无缺失

## 数据来源
- 主来源：今日酒价微信公众号专辑页 (Playwright 方案, 2026-08-12起)
- 备用来源：金价查询网(huangjinjiage.cn)、酱酒界、热贵网、茅酒顾问
- 镜像来源: mffb.com.cn (淘酒帮), 163.com 白酒经销商学院 (《33款名酒全年走势+批零价差》系列)
- ⚠️ 2026-08-06起WeChat文章页反爬升级, CDP/agent-browser/curl均被拦截(返回"参数错误")
- 🔴 2026-08-10起 agent-browser CDP 故障：open 报成功但 eval/snapshot 始终 about:blank（非WeChat变化，是agent-browser自身bug）
- ✅ 2026-08-12 修复：改用 Playwright 直接连 Chrome（baoyu-fetch 同引擎），绕开 agent-browser
  - 脚本: `scripts/fetch_latest_playwright.cjs`（取最新1篇）+ `scripts/fetch_recent_articles.cjs <N>`（取最近N篇，倒序）
  - 依赖: NODE_PATH=/Users/ailubo/.workbuddy/binaries/node/workspace/node_modules，系统Chrome executablePath，baoyu-skills Chrome profile，代理127.0.0.1:7897
  - 主脚本 fetch_latest_wechat_album_item.sh 已改写为 Playwright 方案
- ⚠️ 163.com 镜像自 2026-08-10 起为纯图片(走势曲线图)，无文本表格，不可作 fallback
- 金价查询网提供单日快照数据(飞天/五星/精品/生肖全品类, 散瓶+原件双列)
- 金价查询网数据为单日快照(无昨日/变化), all_prices.jsonl中yesterday/change字段设null

## 文件结构与格式
- `data.json`: **dict结构** `{prices: [{date, yuanxiang, sanping, source, note, signal, guide_price}, ...], note, last_updated}` — 非纯数组，操作前需检查
- `all_prices.jsonl`: 全品类每日行情 (~174条/天)，存在两种格式(嵌套products和扁平per-row)，待统一
- `regenerate.py`: 重新生成月度MD + 总览，依赖data.json的prices数组

## 自动化注意事项
- data.json 操作：先 `isinstance(data, dict)` 检查 → 有 `prices` key → 用 `data['prices']`
- all_prices.jsonl 格式不统一，读取时需兼容两种格式（嵌套products/扁平per-row）
- 追加数据后必须更新 `last_updated` 字段
- ✅ 2026-08-12 起每日更新统一走 `scripts/daily_update.sh` 状态机 runner（SUCCESS/VERIFIED_NOT_PUBLISHED/STALE_NO_PUBLISH/DISCOVERY_FAILED/...）
  - 双检: 14:00 首检 + 20:30 补检（晚间补检 automation-1786517311073）
  - 缺口检测: `scripts/verify_data.py --quiet`（日历 vs data.json vs jsonl；停更例外读 sources/停更例外.md）
  - 防静默失败铁律: 只有 SUCCESS 与 VERIFIED_NOT_PUBLISHED 是正常结果；失败类状态必须告警，禁止用 WebSearch 编造数据
  - 禁止 git add -A（精确暂存 data.json/all_prices.jsonl/2026/*.md/2026总览.md/sources/）；推送后校验 HEAD==origin/main
