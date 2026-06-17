// fetch_all_2025.mjs — One script: launch Chrome, batch fetch via baoyu-fetch CDP
import puppeteer from 'puppeteer-core';
import { spawn } from 'child_process';
import { readFileSync, mkdirSync, existsSync, statSync } from 'fs';
import { join } from 'path';

const CSV   = 'sources/jinri-jiujia-wechat-links/2025-links.csv';
const OUT   = 'sources/jinri-jiujia-wechat-links/2025-articles';
const BUN   = 'C:/Users/PC/.bun/bin/bun.exe';
const CLI   = 'C:/Users/PC/.workbuddy/skills/baoyu-url-to-markdown/scripts/lib/cli.ts';
const PROFILE = 'C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile';

mkdirSync(OUT, { recursive: true });

const lines = readFileSync(CSV, 'utf8').trim().split('\n').slice(1);
const articles = lines.map(l => { const m = l.match(/"([^"]+)","([^"]+)"/); return { date: m[1], url: m[2] }; });

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  userDataDir: PROFILE,
  headless: true,
  args: ['--no-sandbox'],
});
const cdpUrl = browser.wsEndpoint();
console.log(`Chrome ready: ${cdpUrl}`);

let ok = 0, fail = 0, skip = 0;
const t0 = Date.now();

for (let i = 0; i < articles.length; i++) {
  const a = articles[i];
  const outPath = join(OUT, `${a.date}.md`);
  
  if (existsSync(outPath) && statSync(outPath).size > 500) {
    skip++;
    console.log(`[${i+1}/${articles.length}] SKIP ${a.date}`);
    continue;
  }
  
  const result = await fetchOne(a.url, outPath, cdpUrl);
  if (result) ok++; else fail++;
  console.log(`[${i+1}/${articles.length}] ${result?'OK':'FAIL'} ${a.date}`);
}

await browser.close();
const elapsed = (Date.now() - t0) / 60000;
console.log(`\nDone: ${ok} ok, ${skip} skip, ${fail} fail in ${elapsed.toFixed(1)}min`);

function fetchOne(url, outPath, cdpUrl) {
  return new Promise(resolve => {
    const child = spawn(BUN, [CLI, url, '--headless', '--cdp-url', cdpUrl, '--output', outPath, '--timeout', '25000'], {
      stdio: 'pipe',
      env: { ...process.env, BAOYU_CHROME_PROFILE_DIR: PROFILE }
    });
    child.on('close', code => resolve(code === 0 && existsSync(outPath) && statSync(outPath).size > 500));
  });
}
