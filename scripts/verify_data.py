#!/usr/bin/env python3
"""Verify data coverage: calendar vs data.json vs all_prices.jsonl.

Usage:
  verify_data.py                 # full check 2026-01-01..today
  verify_data.py --date 2026-08-12   # check up to a specific date
  verify_data.py --quiet         # machine-readable one-liner (for automation)

Exit codes:
  0 = no actionable gaps
  1 = gaps found (missing dates / cross-file mismatch)
  2 = data files unreadable

Known non-publishing days are read from sources/停更例外.md (one date per line,
'#' comments allowed). Only calendar dates with NO article are excused.
"""

import json
import os
import re
import sys
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
DATA_JSON = os.path.join(BASE, 'data.json')
ALL_PRICES = os.path.join(BASE, 'all_prices.jsonl')
EXCEPTIONS_FILE = os.path.join(BASE, 'sources', '停更例外.md')

DEFAULT_START = date(2026, 1, 1)


def load_exceptions():
    exc = set()
    if os.path.isfile(EXCEPTIONS_FILE):
        with open(EXCEPTIONS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', line)
                if m:
                    exc.add(f'{m.group(1)}-{m.group(2)}-{m.group(3)}')
    return exc


def load_data_dates():
    """Return (dates, sources_by_date)."""
    with open(DATA_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict) or 'prices' not in data:
        raise ValueError('data.json 结构异常: 缺少 prices')
    dates = {p['date'] for p in data['prices']}
    sources = {p['date']: p.get('source', '') for p in data['prices']}
    return dates, sources


def load_jsonl_dates():
    dates = set()
    with open(ALL_PRICES, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = obj.get('date')
            if d:
                dates.add(d)
    return dates


def main():
    quiet = '--quiet' in sys.argv
    end_arg = None
    for i, a in enumerate(sys.argv):
        if a == '--date' and i + 1 < len(sys.argv):
            end_arg = sys.argv[i + 1]

    try:
        data_dates, data_sources = load_data_dates()
        jsonl_dates = load_jsonl_dates()
    except Exception as e:
        print(f'ERROR: {e}')
        sys.exit(2)

    exceptions = load_exceptions()

    if end_arg:
        end = date.fromisoformat(end_arg)
    else:
        end = date.today()
    end = min(end, date.today())

    cur = DEFAULT_START
    calendar = []
    while cur <= end:
        calendar.append(cur.isoformat())
        cur += timedelta(days=1)

    missing_with_article = []   # calendar day missing from data.json but NOT excused
    missing_excused = []        # calendar day missing and listed as 停更例外
    jsonl_gaps = []             # date in data.json but absent from all_prices.jsonl
    jsonl_extra = []            # date in all_prices.jsonl but absent from data.json

    for ds in calendar:
        if ds not in data_dates:
            if ds in exceptions:
                missing_excused.append(ds)
            else:
                missing_with_article.append(ds)

    for ds in sorted(data_dates):
        if ds not in jsonl_dates:
            # 二手来源(财联社/云酒网等)只有核心价、无全品类 → 合理差异，不告警
            if data_sources.get(ds) != '今日酒价':
                continue
            jsonl_gaps.append(ds)
    for ds in sorted(jsonl_dates):
        if ds not in data_dates:
            jsonl_extra.append(ds)

    max_data = max(data_dates) if data_dates else 'N/A'
    max_jsonl = max(jsonl_dates) if jsonl_dates else 'N/A'

    if quiet:
        status = 'OK' if not (missing_with_article or jsonl_gaps) else 'GAPS'
        print(f'{status} data_max={max_data} jsonl_max={max_jsonl} '
              f'missing={len(missing_with_article)} jsonl_gaps={len(jsonl_gaps)} '
              f'excused={len(missing_excused)}')
    else:
        print(f'data.json: {len(data_dates)} dates, max={max_data}')
        print(f'all_prices.jsonl: {len(jsonl_dates)} dates, max={max_jsonl}')
        print(f'停更例外(已核验无文章): {len(missing_excused)} {missing_excused}')
        print(f'待补缺口(有文章但未收录): {len(missing_with_article)}')
        for ds in missing_with_article:
            print(f'  MISSING {ds}')
        print(f'data有但jsonl缺: {len(jsonl_gaps)}')
        for ds in jsonl_gaps:
            print(f'  JSONL_GAP {ds}')
        print(f'jsonl有但data缺: {len(jsonl_extra)}')
        for ds in jsonl_extra:
            print(f'  JSONL_EXTRA {ds}')

    if missing_with_article or jsonl_gaps:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
