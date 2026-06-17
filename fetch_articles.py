#!/usr/bin/env python3
"""Step 1: Batch fetch all 2025 今日酒价 articles via baoyu-fetch as .md files."""
import csv, subprocess, os, time, sys, re

CSV   = 'sources/jinri-jiujia-wechat-links/2025-links.csv'
OUT   = 'sources/jinri-jiujia-wechat-links/2025-articles'
BUN   = 'C:/Users/PC/.bun/bin/bun.exe'
CLI   = 'C:/Users/PC/.workbuddy/skills/baoyu-url-to-markdown/scripts/lib/cli.ts'

os.makedirs(OUT, exist_ok=True)

rows = []
with open(CSV) as f:
    for r in csv.DictReader(f):
        rows.append(r)

total, ok, skip, fail = 0, 0, 0, 0
t0 = time.time()

for idx, row in enumerate(rows):
    date, url = row['date'], row['url']
    out_path = os.path.join(OUT, f'{date}.md')
    
    # Skip already-completed files (> 500 bytes)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 500:
        skip += 1
        continue
    
    total += 1
    sys.stdout.write(f'[{idx+1:3d}/{len(rows)}] {date}  ')
    sys.stdout.flush()
    
    try:
        r = subprocess.run(
            [BUN, CLI, url, '--headless', '--output', out_path, '--timeout', '20000'],
            capture_output=True, timeout=120,
            env={**os.environ, 'BAOYU_CHROME_PROFILE_DIR': 'C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile'}
        )
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 500:
            ok += 1
            sys.stdout.write(f'OK ({os.path.getsize(out_path)//1024}KB)\n')
        else:
            fail += 1
            sys.stdout.write('FAIL\n')
    except subprocess.TimeoutExpired:
        fail += 1
        sys.stdout.write('TIMEOUT\n')
    except Exception as e:
        fail += 1
        sys.stdout.write(f'ERR:{str(e)[:40]}\n')
    
    sys.stdout.flush()

elapsed = time.time() - t0
print(f'\nDone: {total} processed ({ok} ok, {skip} skipped, {fail} failed) in {elapsed/60:.1f}min')
