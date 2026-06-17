// fetch_baoyu.mjs — Batch fetch articles via baoyu-fetch (CDP mode)
import { spawn } from 'child_process';
import { readFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

const CSV = 'sources/jinri-jiujia-wechat-links/2025-links.csv';
const OUT = 'sources/jinri-jiujia-wechat-links/2025-articles';
const BUN = 'C:/Users/PC/.bun/bin/bun.exe';
const CLI = 'C:/Users/PC/.workbuddy/skills/baoyu-url-to-markdown/scripts/lib/cli.ts';
const CDP = readFileSync('.cdp_url', 'utf8').trim();

mkdirSync(OUT, { recursive: true });

const lines = readFileSync(CSV, 'utf8').trim().split('\n').slice(1); // skip header
const articles = lines.map(l => {
  const m = l.match(/"([^"]+)","([^"]+)"/);
  return { date: m[1], url: m[2] };
});

let ok = 0, fail = 0, skip = 0;
const t0 = Date.now();

async function fetchOne(article, idx) {
  const out = join(OUT, `${article.date}.md`);
  if (existsSync(out)) { skip++; return; }
  
  return new Promise(resolve => {
    const child = spawn(BUN, [CLI, article.url, '--headless', '--cdp-url', CDP, '--output', out, '--timeout', '25000'], {
      stdio: 'pipe',
      env: { ...process.env, BAOYU_CHROME_PROFILE_DIR: 'C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile' }
    });
    
    child.on('close', code => {
      if (code === 0 && existsSync(out)) ok++;
      else fail++;
      resolve();
    });
  });
}

// Sequential to avoid CDP conflicts
for (let i = 0; i < articles.length; i++) {
  const a = articles[i];
  await fetchOne(a, i);
  process.stdout.write(`[${String(i+1).padStart(3)}/${articles.length}] ${a.date} ${ok+fail+skip>i? (existsSync(join(OUT,a.date+'.md'))?'OK':'FAIL') : '...'}\r`);
}
console.log(`\nDone: ${ok} ok, ${skip} skip, ${fail} fail in ${((Date.now()-t0)/60000).toFixed(1)}min`);
