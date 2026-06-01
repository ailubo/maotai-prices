import json, os, re

BASE = r'c:\Users\PC\WorkBuddy\Claw\maotai-prices'

def signal(sp):
    """🔴 <1539 | 🟡 1539~1800 | 🟢 >1800 | null if no data"""
    if sp is None: return None
    # Handle strings like "⚠️1610" or "1460~1520"
    if isinstance(sp, str):
        nums = [float(n) for n in re.findall(r'\d+', sp)]
        if not nums: return None
        sp = sum(nums) / len(nums)  # average if range
    if sp < 1539: return '🔴'
    if sp > 1800: return '🟢'
    return '🟡'

# Load
with open(f'{BASE}/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Add signal to each entry
for p in data['prices']:
    p['signal'] = signal(p['sanping'])

# Update note
data['note'] = '信号: 🔴<1539(跌破零售价) 🟡1539~1800 🟢>1800 | ⚠️=推算 | 空=无公开报道'
data['last_updated'] = '2026-06-01T16:45:00+08:00'

with open(f'{BASE}/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Stats
signals = [p['signal'] for p in data['prices'] if p['signal']]
red = signals.count('🔴')
green = signals.count('🟢')
yellow = signals.count('🟡')
nulls = len([p for p in data['prices'] if p['signal'] is None])

print(f'Signals: {red}🔴 {green}🟢 {yellow}🟡 {nulls}null')

# Regenerate Markdown table with signal column
lines = []
lines.append('# 2026年飞天茅台散瓶 vs 原箱 批价对比')
lines.append('')
lines.append('> 信号: 🔴<1539（跌破官方零售价） 🟡1539~1800 🟢>1800')
lines.append('> 标注: ★=散瓶+原箱配对日 | ⚠️=推算 | 🔴=罕见异常')
lines.append('> 数据截止: 2026-06-01')
lines.append('')
lines.append('| 日期 | 信号 | 散瓶 | 原箱 | 价差 | 来源 | 备注 |')
lines.append('|------|:--:|------|------|------|------|------|')

for p in data['prices']:
    d = p['date']
    s = p['signal'] or ''
    sp = p['sanping']
    yx = p['yuanxiang']
    src = p['source'][:15]
    note = p['note'][:30]
    
    # Format prices
    def fmt(v):
        if v is None: return '—'
        if isinstance(v, str): return v
        return str(v)
    
    sp_f = fmt(sp)
    yx_f = fmt(yx)
    
    # Calculate spread if both are numeric
    spread = '—'
    if isinstance(sp, (int,float)) and isinstance(yx, (int,float)):
        spread = str(yx - sp)
    
    # Tag paired days
    if sp is not None and yx is not None and isinstance(sp,(int,float)) and isinstance(yx,(int,float)):
        d = f'★ {d}'
    
    lines.append(f'| {d} | {s} | {sp_f} | {yx_f} | {spread} | {src} | {note} |')

# Monthly summaries
lines.append('')
lines.append('## 月度信号分布')
lines.append('')
lines.append('| 月份 | 🔴 | 🟡 | 🟢 | 无数据 |')
lines.append('|------|:--:|:--:|:--:|:--:|')

months = {}
for p in data['prices']:
    m = p['date'][:7]
    if m not in months:
        months[m] = {'🔴':0,'🟡':0,'🟢':0,'-':0}
    key = p['signal'] if p['signal'] else '-'
    months[m][key] += 1

for m in sorted(months):
    c = months[m]
    lines.append(f'| {m} | {c["🔴"]} | {c["🟡"]} | {c["🟢"]} | {c["-"]} |')

with open(f'{BASE}/2026-原箱vs散瓶对比.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('Markdown regenerated')
