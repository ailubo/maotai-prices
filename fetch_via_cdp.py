#!/usr/bin/env python3
"""Batch fetch via baoyu-fetch using a single shared Chrome via CDP."""
import csv, subprocess, os, time, sys, json
import subprocess as sp

CSV   = 'sources/jinri-jiujia-wechat-links/2025-links.csv'
OUT   = 'sources/jinri-jiujia-wechat-links/2025-articles'
BUN   = 'C:/Users/PC/.bun/bin/bun.exe'
CLI   = 'C:/Users/PC/.workbuddy/skills/baoyu-url-to-markdown/scripts/lib/cli.ts'
PROFILE = 'C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile'

os.makedirs(OUT, exist_ok=True)

def get_cdp_url():
    """Launch Chrome via Node (puppeteer), return CDP wsEndpoint."""
    node_script = """
import('puppeteer-core').then(async ({default: puppeteer}) => {
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    userDataDir: 'C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile',
    headless: true,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    ignoreDefaultArgs: ['--enable-automation'],
  });
  console.log(b.wsEndpoint());
});
"""
    r = sp.run(['C:/Users/PC/.workbuddy/binaries/node/versions/22.22.2/node.exe', '-e', node_script],
               capture_output=True, text=True, timeout=30,
               cwd='C:/Users/PC/WorkBuddy/Claw/maotai-prices')
    if r.returncode != 0:
        sys.stderr.write(f'Chrome launch failed: {r.stderr}')
        sys.exit(1)
    return r.stdout.strip()

print('Launching shared Chrome...', flush=True)
cdp = get_cdp_url()
assert cdp.startswith('ws://'), f'Bad CDP URL: {cdp}'
print(f'CDP: {cdp}', flush=True)

rows = []
with open(CSV) as f:
    for r in csv.DictReader(f):
        rows.append(r)

ok = fail = skip = 0
t0 = time.time()

for idx, row in enumerate(rows):
    date, url = row['date'], row['url']
    out_path = os.path.join(OUT, f'{date}.md')
    
    if os.path.exists(out_path) and os.path.getsize(out_path) > 500:
        skip += 1
        continue
    
    sys.stdout.write(f'[{idx+1:3d}/{len(rows)}] {date}  ')
    sys.stdout.flush()
    
    try:
        r = sp.run([
            BUN, CLI, url,
            '--headless', '--cdp-url', cdp,
            '--output', out_path, '--timeout', '25000'
        ], capture_output=True, timeout=45,
           env={**os.environ, 'BAOYU_CHROME_PROFILE_DIR': PROFILE})
        
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 500:
            ok += 1
            sys.stdout.write(f'OK ({os.path.getsize(out_path)//1024}KB)\n')
        else:
            fail += 1
            sys.stdout.write(f'FAIL ret={r.returncode}\n')
    except sp.TimeoutExpired:
        fail += 1
        sys.stdout.write('TIMEOUT\n')
    except Exception as e:
        fail += 1
        sys.stdout.write(f'ERR\n')
    
    sys.stdout.flush()

elapsed = time.time() - t0
print(f'\nDone: {ok} ok, {skip} skipped, {fail} failed in {elapsed/60:.1f}min')
