import json, os, re, sys
from datetime import date, datetime, timezone, timedelta

# 让 emoji 信号能打印到任意控制台（GBK 控制台下原 print 会 UnicodeEncodeError，且会崩在写 data.json 之前 → 静默失败）
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# 脚本所在目录（可移植，不再硬编码绝对路径）
BASE = os.path.dirname(os.path.abspath(__file__))
with open(f'{BASE}/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 指导价历史（数据驱动；下次指导价再变只加一行，不改下面的计算逻辑）
GUIDE_PRICE_HISTORY = [
    {'valid_from': '2026-01-01', 'valid_until': '2026-03-30', 'price': 1499},
    {'valid_from': '2026-03-31', 'valid_until': None,         'price': 1539},
]

def guide_price_for(d):
    """按日期查当期指导价（取最后一个 valid_from <= d 的档）"""
    gp = GUIDE_PRICE_HISTORY[0]['price']
    for seg in GUIDE_PRICE_HISTORY:
        if d >= date.fromisoformat(seg['valid_from']):
            gp = seg['price']
    return gp

# === 数据校验（异常即报错，不静默污染序列）===
_seen = set()
for _p in data['prices']:
    _dt = _p['date']
    date.fromisoformat(_dt)                      # 日期格式非法会抛错
    if _dt in _seen:
        raise ValueError(f"data.json 有重复日期: {_dt}")
    _seen.add(_dt)
    _sp = _p.get('sanping')
    if isinstance(_sp, (int, float)) and not (1000 <= _sp <= 3000):
        raise ValueError(f"散瓶批价异常 {_dt}: {_sp}（应在 1000-3000，疑似多打/少打一位）")
_latest_date = max(_seen) if _seen else datetime.now().strftime('%Y-%m-%d')

# === 更新 JSON：加 guide_price + 重新算 signal ===
for p in data['prices']:
    d = date.fromisoformat(p['date'])
    p['guide_price'] = guide_price_for(d)
    
    sp = p['sanping']
    if sp is None:
        p['signal'] = None
        continue
    
    # 处理字符串型（范围/推算）
    if isinstance(sp, str):
        nums = [float(n) for n in re.findall(r'\d+', sp)]
        if not nums:
            p['signal'] = None
            continue
        sp = sum(nums) / len(nums)  # 取平均
    
    if sp < p['guide_price']:
        p['signal'] = '🔴'
    elif sp > 1800:
        p['signal'] = '🟢'
    else:
        p['signal'] = '🟡'

data['note'] = '🔴=低于当期指导价(1499→3/31→1539) | 🟡=指导价~1800 | 🟢=>1800'
data['last_updated'] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
data['guide_price_history'] = GUIDE_PRICE_HISTORY

# 统计
signals = [p['signal'] for p in data['prices'] if p['signal']]
print(f'Signals: {signals.count("🔴")}🔴 {signals.count("🟡")}🟡 {signals.count("🟢")}🟢')

with open(f'{BASE}/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('data.json updated')

# === 生成各月 MD ===
def fmt(v):
    if v is None: return '—'
    if isinstance(v, (int, float)): return str(int(v)) if v == int(v) else str(v)
    return str(v)

 

# 按月分组
months = {}
for p in data['prices']:
    m = p['date'][:7]
    months.setdefault(m, []).append(p)

for m in sorted(months):
    lines = []
    lines.append(f'# {m.replace("-", "年")}月 — 飞天茅台批价')
    lines.append('')
    
    # 当月指导价（取第一个数据点的指导价）
    gp = months[m][0]['guide_price']
    lines.append(f'> 指导价: ¥{gp} | 🔴=低于指导价 | 🟡=指导价~1800 | 🟢=>1800')
    lines.append(f'> 数据截止: {_latest_date} | 当月收录 {len(months[m])} 个数据点')
    lines.append('')
    lines.append('| 日期 | 散瓶 | 原箱 | 指导价 | 信号 | 来源 |')
    lines.append('|------|------|------|--------|:--:|------|')
    
    for p in months[m]:
        d = p['date'][-5:]
        sp = fmt(p['sanping'])
        yx = fmt(p['yuanxiang'])
        gp_f = str(p['guide_price'])
        sig = p['signal'] or ''
        src = p['source'][:15]
        lines.append(f'| {d} | {sp} | {yx} | ¥{gp_f} | {sig} | {src} |')
    
    fp = f'{BASE}/2026/{m}.md'
    with open(fp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  {m}.md ({len(months[m])} rows)')

# === 重新生成年度对比表（和月度格式统一） ===
lines = []
lines.append('# 2026年飞天茅台批价总览')
lines.append('')
lines.append('> 🔴=低于当期指导价 | 🟡=指导价~1800 | 🟢=>1800')
lines.append('> 指导价: ¥1,499 (1/1~3/30) → ¥1,539 (3/31起)')
lines.append('> ★=散瓶+原箱配对 | ⚠️=推算')
lines.append('')
lines.append('| 日期 | 散瓶 | 原箱 | 指导价 | 信号 | 来源 | 备注 |')
lines.append('|------|------|------|--------|:--:|------|------|')

for p in data['prices']:
    d = p['date'][-5:]
    sp = fmt(p['sanping'])
    yx = fmt(p['yuanxiang'])
    gp_f = str(p['guide_price'])
    sig = p['signal'] or ''
    src = p['source'][:15]
    note = p.get('note', '')[:25]
    lines.append(f'| {d} | {sp} | {yx} | ¥{gp_f} | {sig} | {src} | {note} |')

with open(f'{BASE}/2026总览.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('2026总览.md regenerated')
