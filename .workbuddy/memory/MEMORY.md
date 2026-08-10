# maotai-prices 项目长期记忆

## 全品类解析规范
- **td级解析**：按`<td>`分组而非`<span>`，先合并每个td内所有span
- **列数识别**：标准表4列(品名/规格/昨日/今日)，年份酒/生肖/老酒3列(品名/规格/行情)
- **清洗规则**：`re.sub(r'&nbsp;|\u00a0|[⬆⬇➡]', '', text).strip()`
- **校验**：解析后检查 today>0 和已知product无缺失

## 数据来源
- 主来源：今日酒价微信公众号专辑页 (agent-browser + baoyu-fetch)
- 备用来源：金价查询网(huangjinjiage.cn)、酱酒界、热贵网、茅酒顾问
- 镜像来源: mffb.com.cn (淘酒帮), 163.com 白酒经销商学院 (《33款名酒全年走势+批零价差》系列)
- ⚠️ 2026-08-06起WeChat文章页反爬升级, CDP/agent-browser/curl均被拦截(返回"参数错误")
- 2026-08-10: agent-browser 严重异常：open 报成功但 eval/snapshot 始终 about:blank，即使 example.com 也复现
- 2026-08-10: baoyu-fetch 仍可用但只能拿专辑页前20条（按时间正序）
- 金价查询网提供单日快照数据(飞天/五星/精品/生肖全品类, 散瓶+原件双列)
- 金价查询网数据为单日快照(无昨日/变化), all_prices.jsonl中yesterday/change字段设null
- mffb.com.cn 163.com 镜像含完整173款名酒批价表(可作主源fallback)

## 文件结构与格式
- `data.json`: **dict结构** `{prices: [{date, yuanxiang, sanping, source, note, signal, guide_price}, ...], note, last_updated}` — 非纯数组，操作前需检查
- `all_prices.jsonl`: 全品类每日行情 (~174条/天)，存在两种格式(嵌套products和扁平per-row)，待统一
- `regenerate.py`: 重新生成月度MD + 总览，依赖data.json的prices数组

## 自动化注意事项
- data.json 操作：先 `isinstance(data, dict)` 检查 → 有 `prices` key → 用 `data['prices']`
- all_prices.jsonl 格式不统一，读取时需兼容两种格式
- 追加数据后必须更新 `last_updated` 字段
