#!/usr/bin/env python3
"""Parse baoyu-fetch markdown output and extract all product prices for a date.

Hardening (2026-08-12, per codex audit P0-4/P0-5):
- Article date must be exact & explicit: NEVER fall back to "today".
- Core prices (26年飞天散/原) must be integers in a sane range.
- Product count must meet a recent baseline; known core products must exist.
- data.json + all_prices.jsonl updated atomically (temp file + os.replace).
- Exit codes: 0 = written, 1 = validation failed (nothing written), 2 = article date mismatch.
"""

import json
import os
import re
import sys
import tempfile
from html.parser import HTMLParser
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.environ.get('MAOTAI_MD_PATH', os.path.join('/tmp', 'baoyu_today.md'))
# Expected article date; if unset, we require the article itself to carry a valid 2026 date.
EXPECT_DATE = os.environ.get('MAOTAI_EXPECT_DATE', '')
SANITY_RANGE = (1000, 6000)      # core price sanity band (元/瓶)
MIN_PRODUCTS = 50                # minimum product rows per article (baseline)
REQUIRED_PRODUCTS = ['26年飞天(散)', '26年飞天(原)']
GUIDE_PRICE = 1539

# --- HTML table parsing (td-level, brand header in first row) ---
KNOWN_BRANDS = [
    '个性茅台', '茅台酱香', '五粮液', '茅台', '习酒', '汾酒', '洋河', '水井坊',
    '泸州老窖', '古井贡', '西凤', '茅台集团', '珍酒', '仰韶', '杜康', '潭酒',
    '郎酒', '酒鬼', '宝丰', '丹泉', '剑南春', '舍得', '国台', '安酒',
    '同茂兴', '金沙', '董酒',
]


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.cur_td = []
        self.cur_row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
            self.cur_td = []

    def handle_endtag(self, tag):
        if tag == 'td' and self.in_td:
            self.in_td = False
            text = ''.join(self.cur_td)
            text = re.sub(r'&nbsp;|\u00a0|[⬆⬇➡]', '', text).strip()
            self.cur_row.append(text)
        elif tag == 'tr' and self.cur_row:
            self.rows.append(list(self.cur_row))
            self.cur_row = []

    def handle_data(self, data):
        if self.in_td:
            self.cur_td.append(data)


def parse_tables(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    tables = re.findall(r'<table[^>]*>.*?</table>', content, re.DOTALL)
    parsed = []
    for th in tables:
        p = TableParser()
        p.feed(th)
        parsed.append(p.rows)
    return parsed


def detect_brand(header_row):
    for cell in header_row:
        text = cell.strip()
        if not text or text in ('品名', '规格', '昨日行情', '今日行情', '产品参数', '单瓶价'):
            continue
        if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日', text):
            continue
        if '公众号' in text or '今日酒价' in text:
            continue
        for b in KNOWN_BRANDS:
            if b in text:
                return b
        if not re.match(r'^[\d\s]+$', text):
            return text
    return None


def extract_products(rows):
    if not rows:
        return None, []
    brand = detect_brand(rows[0])
    header_idx = -1
    for i, row in enumerate(rows):
        if any('品名' in c for c in row):
            header_idx = i
            break
    if header_idx < 0:
        return brand, []

    header = rows[header_idx]
    ncols = len(header)
    has_yesterday = any('昨日' in c for c in header)
    has_today = any('今日' in c for c in header)

    products = []
    for row in rows[header_idx + 1:]:
        if len(row) < 2:
            continue
        name = row[0].strip()
        if not name or name in ('品名', '品牌'):
            continue
        spec = row[1].strip() if len(row) > 1 else ''
        if not spec:
            continue
        if has_yesterday and has_today:
            y_col = next((j for j, c in enumerate(header) if '昨日' in c), 2)
            t_col = next((j for j, c in enumerate(header) if '今日' in c), 3)
            yesterday = row[y_col].strip() if y_col < len(row) else ''
            today = row[t_col].strip() if t_col < len(row) else ''
            if not yesterday and not today:
                continue
        elif ncols >= 3 and not has_yesterday:
            price = row[2].strip() if len(row) > 2 else ''
            if not price:
                continue
            yesterday = ''
            today = price
        else:
            continue
        products.append({'name': name, 'spec': spec, 'yesterday': yesterday, 'today': today})
    return brand, products


def to_int(v):
    m = re.match(r'^\s*(\d+(?:\.\d+)?)', str(v))
    return int(float(m.group(1))) if m else None


def article_date(md_path):
    """Extract the article's own date. Returns None if not found."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', content)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"


def main():
    if not os.path.isfile(MD_PATH):
        print(f'FAIL: 正文文件不存在: {MD_PATH}', file=sys.stderr)
        sys.exit(1)

    # 1. Date validation: article date must be present and (if expected) exact match
    adate = article_date(MD_PATH)
    if adate is None:
        print('FAIL: 正文中找不到发布日期 (4位年份+月+日)，禁止落盘', file=sys.stderr)
        sys.exit(1)
    if not adate.startswith('2026-'):
        print(f'FAIL: 正文日期非2026年: {adate}，禁止落盘', file=sys.stderr)
        sys.exit(1)
    if EXPECT_DATE and adate != EXPECT_DATE:
        print(f'FAIL: 正文日期 {adate} != 期望日期 {EXPECT_DATE}，禁止落盘', file=sys.stderr)
        sys.exit(2)
    print(f'Article date: {adate}')

    # 2. Parse all tables
    all_products = []
    seen = set()
    for rows in parse_tables(MD_PATH):
        brand, products = extract_products(rows)
        for p in products:
            key = (brand or '其他', p['name'], p['spec'])
            if key not in seen:
                seen.add(key)
                all_products.append({**p, 'brand': brand or '其他'})

    print(f'Parsed {len(all_products)} products')

    # 3. Core price validation (hard gate)
    sanping = None
    yuanxiang = None
    for p in all_products:
        if p['name'] == '26年飞天(散)':
            sanping = to_int(p['today'])
        if p['name'] == '26年飞天(原)':
            yuanxiang = to_int(p['today'])

    errors = []
    if sanping is None:
        errors.append('核心产品缺失: 26年飞天(散)')
    elif not (SANITY_RANGE[0] <= sanping <= SANITY_RANGE[1]):
        errors.append(f'散瓶价格越界: {sanping} 不在 {SANITY_RANGE} 区间')
    if yuanxiang is None:
        errors.append('核心产品缺失: 26年飞天(原)')
    elif not (SANITY_RANGE[0] <= yuanxiang <= SANITY_RANGE[1]):
        errors.append(f'原箱价格越界: {yuanxiang} 不在 {SANITY_RANGE} 区间')

    for req in REQUIRED_PRODUCTS:
        if not any(p['name'] == req for p in all_products):
            errors.append(f'已知核心产品缺失: {req}')

    if len(all_products) < MIN_PRODUCTS:
        errors.append(f'产品数过少: {len(all_products)} < 基线 {MIN_PRODUCTS}')

    if errors:
        print('FAIL: ' + '; '.join(errors), file=sys.stderr)
        sys.exit(1)

    print(f'散瓶: {sanping}, 原箱: {yuanxiang}, 产品数: {len(all_products)}')

    # 4. Load data.json (dict structure), build in-memory candidates
    data_path = f'{BASE}/data.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert isinstance(data, dict) and 'prices' in data, 'data.json 结构异常'

    existing_dates = {p['date'] for p in data['prices']}
    if adate in existing_dates:
        print(f'Date {adate} already exists in data.json, skipping')
        sys.exit(0)

    signal = '🔴' if sanping < GUIDE_PRICE else ('🟡' if sanping <= 1800 else '🟢')
    entry = {
        'date': adate,
        'yuanxiang': yuanxiang,
        'sanping': sanping,
        'source': '今日酒价',
        'guide_price': GUIDE_PRICE,
        'signal': signal,
        'note': '',
    }
    new_prices = sorted(data['prices'] + [entry], key=lambda p: p['date'])
    new_data = dict(data)
    new_data['prices'] = new_prices
    new_data['last_updated'] = adate

    # 5. Build jsonl candidates (flat per-row)
    jl_path = f'{BASE}/all_prices.jsonl'
    new_lines = []
    for p in all_products:
        new_lines.append(json.dumps({
            'date': adate,
            'brand': p['brand'],
            'name': p['name'],
            'spec': p['spec'],
            'yesterday': p['yesterday'],
            'today': p['today'],
        }, ensure_ascii=False))

    # 6. Atomic writes: temp file + os.replace, jsonl first then data.json
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix='.tmp')
    try:
        with os.fdopen(fd, 'a', encoding='utf-8') as tf:
            # append existing jsonl content + new lines
            with open(jl_path, 'r', encoding='utf-8') as jf:
                tf.write(jf.read())
            for line in new_lines:
                tf.write(line + '\n')
        os.replace(tmp, jl_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    fd2, tmp2 = tempfile.mkstemp(dir=BASE, suffix='.tmp')
    try:
        with os.fdopen(fd2, 'w', encoding='utf-8') as tf:
            json.dump(new_data, tf, ensure_ascii=False, indent=2)
        os.replace(tmp2, data_path)
    except Exception:
        try:
            os.unlink(tmp2)
        except OSError:
            pass
        raise

    print(f'Written {adate} (散={sanping} 原={yuanxiang} {signal}) to data.json + all_prices.jsonl ({len(new_lines)} rows)')
    sys.exit(0)


if __name__ == '__main__':
    main()
