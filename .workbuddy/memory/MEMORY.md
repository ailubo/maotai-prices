# maotai-prices 项目长期记忆

## 全品类解析规范
- **td级解析**：按`<td>`分组而非`<span>`，先合并每个td内所有span
- **列数识别**：标准表4列(品名/规格/昨日/今日)，年份酒/生肖/老酒3列(品名/规格/行情)
- **清洗规则**：`re.sub(r'&nbsp;|\u00a0|[⬆⬇➡]', '', text).strip()`
- **校验**：解析后检查 today>0 和已知product无缺失

## 数据来源
- 主来源：今日酒价微信公众号专辑页 (agent-browser + baoyu-fetch)
- 备用来源：金价查询网、酱酒界、热贵网、茅酒顾问

## 文件结构
- `data.json`: 飞天茅台散瓶/原箱价格序列
- `all_prices.jsonl`: 全品类每日行情 (174条/天)
- `regenerate.py`: 重新生成月度MD + 总览
