#!/usr/bin/env python3
"""Parse baoyu-fetch markdown output and extract all product prices for today."""

import json, re, sys, os
from html.parser import HTMLParser
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(os.environ.get('TEMP', '/tmp'), 'baoyu_today.md')
TODAY = date.today().isoformat()  # YYYY-MM-DD

# Read markdown
with open(MD_PATH, 'r', encoding='utf-8') as f:
    md = f.read()

# Extract date from content
date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', md)
if date_match:
    y, m, d = date_match.groups()
    ARTICLE_DATE = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
else:
    ARTICLE_DATE = TODAY
print(f"Article date: {ARTICLE_DATE}")

# Extract all HTML tables
tables = re.findall(r'<table[^>]*>.*?</table>', md, re.DOTALL)

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.current_td_texts = []
        self.current_row = []
        self.rows = []
        self.current_tag_stack = []
        self.current_span_texts = []
        self.in_span = False

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
            self.current_span_texts = []
            self.in_span = False
        elif tag == 'span':
            self.in_span = True

    def handle_endtag(self, tag):
        if tag == 'td' and self.in_td:
            self.in_td = False
            # Flush: combine all span texts in this td
            td_text = ''.join(self.current_span_texts).strip()
            # Clean nbsp and arrows
            td_text = re.sub(r'&nbsp;|\u00a0|[⬆⬇➡]', '', td_text).strip()
            self.current_row.append(td_text)
        elif tag == 'span' and self.in_span:
            self.in_span = False
        elif tag == 'tr' and self.current_row:
            self.rows.append(list(self.current_row))
            self.current_row = []

    def handle_data(self, data):
        if self.in_td:
            if self.in_span:
                self.current_span_texts.append(data)
            else:
                # Data directly in td (not in span) - add anyway for robustness
                self.current_span_texts.append(data)

def parse_table(html):
    parser = TableParser()
    parser.feed(html)
    return parser.rows

all_products = []
seen_products = set()

for table_html in tables:
    rows = parse_table(table_html)
    
    # Find header row (contains 品名)
    header_idx = -1
    for i, row in enumerate(rows):
        if any('品名' in cell for cell in row):
            header_idx = i
            break
    
    if header_idx < 0:
        continue
    
    # Determine number of columns
    header = rows[header_idx]
    ncols = len(header)
    
    # Find column indices
    name_col = 0
    spec_col = 1
    yesterday_col = None
    today_col = None
    
    for j, cell in enumerate(header):
        if '昨日' in cell:
            yesterday_col = j
        if '今日' in cell:
            today_col = j
    
    if yesterday_col is None or today_col is None:
        # Try 3-column format (品名/规格/行情)
        if ncols == 3:
            # year/wine/shengxiao/old_wine tables: 品名/规格/行情
            price_col = 2
            for row in rows[header_idx+1:]:
                if len(row) >= 3:
                    name = row[0].strip()
                    spec = row[1].strip()
                    price = row[2].strip()
                    if name and name != '品名' and spec:
                        key = f"{name}|{spec}"
                        if key not in seen_products:
                            seen_products.add(key)
                            # For 3-col tables we cannot distinguish yesterday/today
                            # Just record the single price
                            all_products.append({
                                'name': name,
                                'spec': spec,
                                'yesterday': '',
                                'today': price
                            })
        continue
    
    # 4-column format: 品名/规格/昨日/今日
    for row in rows[header_idx+1:]:
        if len(row) < max(yesterday_col, today_col) + 1:
            continue
        name = row[name_col].strip() if name_col < len(row) else ''
        spec = row[spec_col].strip() if spec_col < len(row) else ''
        yesterday = row[yesterday_col].strip() if yesterday_col < len(row) else ''
        today = row[today_col].strip() if today_col < len(row) else ''
        
        # Skip header rows and empty rows
        if not name or name in ('品名', '品牌', ''):
            continue
        if not spec:
            continue
        # Skip if it looks like a section header
        if not yesterday and not today:
            continue
        # Skip rows where prices are just styling
        if name in ('昨日行情', '今日行情'):
            continue
            
        key = f"{name}|{spec}"
        if key not in seen_products:
            seen_products.add(key)
            all_products.append({
                'name': name,
                'spec': spec,
                'yesterday': yesterday,
                'today': today
            })

print(f"Parsed {len(all_products)} products")

# Extract key prices for data.json
sanping_price = None
yuanxiang_price = None

for p in all_products:
    nm = p['name']
    if '26年飞天(散)' in nm:
        try:
            sanping_price = int(p['today'])
        except ValueError:
            sanping_price = p['today']
    if '26年飞天(原)' in nm:
        try:
            yuanxiang_price = int(p['today'])
        except ValueError:
            yuanxiang_price = p['today']

print(f"散瓶: {sanping_price}, 原箱: {yuanxiang_price}")

# === Update data.json ===
with open(f'{BASE}/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

existing_dates = {p['date'] for p in data['prices']}
print(f"Existing dates in data.json: {len(existing_dates)}")

if ARTICLE_DATE in existing_dates:
    print(f"Date {ARTICLE_DATE} already exists in data.json, skipping")
else:
    entry = {
        "date": ARTICLE_DATE,
        "yuanxiang": yuanxiang_price,
        "sanping": sanping_price,
        "source": "今日酒价"
    }
    data['prices'].append(entry)
    with open(f'{BASE}/data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Added {ARTICLE_DATE} to data.json")

# === Update all_prices.jsonl ===
jl_path = f'{BASE}/all_prices.jsonl'
existing_jl_dates = set()
if os.path.isfile(jl_path):
    with open(jl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    existing_jl_dates.add(obj.get('date', ''))
                except:
                    pass

if ARTICLE_DATE in existing_jl_dates:
    print(f"Date {ARTICLE_DATE} already exists in all_prices.jsonl, skipping")
else:
    jl_entry = {
        'date': ARTICLE_DATE,
        'source': '今日酒价',
        'product_count': len(all_products),
        'products': all_products
    }
    with open(jl_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(jl_entry, ensure_ascii=False) + '\n')
    print(f"Added {ARTICLE_DATE} to all_prices.jsonl with {len(all_products)} products")

print("Done!")
