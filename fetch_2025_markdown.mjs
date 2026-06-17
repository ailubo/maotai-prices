// Fetch verified 2025 今日酒价 WeChat article URLs to markdown via baoyu-fetch.
// Outputs: sources/jinri-jiujia-wechat-links/2025-md/YYYY-MM-DD.md

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const DEFAULT_LINKS = path.join(ROOT, 'sources/jinri-jiujia-wechat-links/2025-links.json');
const DEFAULT_OUT_DIR = path.join(ROOT, 'sources/jinri-jiujia-wechat-links/2025-md');
const DEFAULT_STATE = path.join(ROOT, 'sources/jinri-jiujia-wechat-links/2025-md-state.json');

const BUN = process.env.BUN || 'C:/Users/PC/.bun/bin/bun.exe';
const BAOYU_CLI = process.env.BAOYU_FETCH_CLI || 'C:/Users/PC/.codex/skills/baoyu-url-to-markdown/scripts/lib/cli.ts';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const CHROME_PROFILE = process.env.CHROME_PROFILE_DIR || 'C:/Users/PC/AppData/Roaming/baoyu-skills/chrome-profile';
const BAOYU_CDP_URL = process.env.BAOYU_CDP_URL || '';
const FETCH_TIMEOUT_MS = Number(process.env.BAOYU_FETCH_TIMEOUT_MS || 140_000);
const PAGE_TIMEOUT_MS = Number(process.env.BAOYU_PAGE_TIMEOUT_MS || 30_000);
const MIN_GOOD_BYTES = Number(process.env.BAOYU_MIN_GOOD_BYTES || 8_000);

const argv = process.argv.slice(2);
let limit = null;
let maxFetch = null;
let force = false;
let linksFile = DEFAULT_LINKS;
let outDir = DEFAULT_OUT_DIR;
let batchSize = Number(process.env.BAOYU_BATCH_SIZE || 8);
let restMs = Number(process.env.BAOYU_BATCH_REST_MS || 60_000);
let delayMinMs = Number(process.env.BAOYU_DELAY_MIN_MS || 5_000);
let delayMaxMs = Number(process.env.BAOYU_DELAY_MAX_MS || 10_000);
let noDelay = false;

for (let i = 0; i < argv.length; i++) {
  const arg = argv[i];
  if (arg === '--limit') {
    limit = Number(argv[++i]);
  } else if (arg === '--max-fetch') {
    maxFetch = Number(argv[++i]);
  } else if (arg === '--force') {
    force = true;
  } else if (arg === '--links') {
    linksFile = path.resolve(argv[++i]);
  } else if (arg === '--out-dir') {
    outDir = path.resolve(argv[++i]);
  } else if (arg === '--batch-size') {
    batchSize = Number(argv[++i]);
  } else if (arg === '--rest-ms') {
    restMs = Number(argv[++i]);
  } else if (arg === '--delay-min-ms') {
    delayMinMs = Number(argv[++i]);
  } else if (arg === '--delay-max-ms') {
    delayMaxMs = Number(argv[++i]);
  } else if (arg === '--no-delay') {
    noDelay = true;
  } else {
    throw new Error(`Unknown argument: ${arg}`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function randomDelay() {
  if (noDelay) return 0;
  const min = Math.max(0, Math.min(delayMinMs, delayMaxMs));
  const max = Math.max(min, delayMaxMs);
  return min + Math.floor(Math.random() * (max - min + 1));
}

function fmtDuration(ms) {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`;
}

function readJson(file) {
  const raw = fs.readFileSync(file, 'utf8');
  const parsed = JSON.parse(raw);
  return typeof parsed === 'string' ? JSON.parse(parsed) : parsed;
}

function isGoodMarkdown(file, expectedDate) {
  if (!fs.existsSync(file)) return false;
  const stat = fs.statSync(file);
  if (stat.size < MIN_GOOD_BYTES) return false;
  const md = fs.readFileSync(file, 'utf8');
  const chineseDate = expectedDate.replace(/^(\d{4})-(\d{2})-(\d{2})$/, (_, y, m, d) => {
    return `${y}年${Number(m)}月${Number(d)}日`;
  });
  return md.includes('今日酒价') && md.includes('<table') && (md.includes(expectedDate) || md.includes(chineseDate));
}

function taskkill(pid) {
  return new Promise(resolve => {
    const killer = spawn('taskkill.exe', ['/PID', String(pid), '/T', '/F'], {
      stdio: 'ignore',
      windowsHide: true,
    });
    killer.on('exit', () => resolve());
    killer.on('error', () => resolve());
  });
}

async function runBaoyu(article, outputFile) {
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  const args = [
    BAOYU_CLI,
    article.link,
    '--headless',
    '--output', outputFile,
    '--timeout', String(PAGE_TIMEOUT_MS),
  ];
  if (BAOYU_CDP_URL) {
    args.push('--cdp-url', BAOYU_CDP_URL);
  } else {
    args.push('--browser-path', CHROME, '--chrome-profile-dir', CHROME_PROFILE);
  }

  const child = spawn(BUN, args, {
    cwd: ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  let stdout = '';
  let stderr = '';
  let killedAfterWrite = false;
  child.stdout.on('data', chunk => { stdout += chunk.toString(); });
  child.stderr.on('data', chunk => { stderr += chunk.toString(); });

  const earlyDone = setInterval(async () => {
    if (!killedAfterWrite && isGoodMarkdown(outputFile, article.date)) {
      killedAfterWrite = true;
      await taskkill(child.pid);
    }
  }, 1000);

  let timedOut = false;
  const timer = setTimeout(async () => {
    timedOut = true;
    await taskkill(child.pid);
  }, FETCH_TIMEOUT_MS);

  const exitCode = await new Promise(resolve => {
    child.on('exit', code => resolve(code));
    child.on('error', () => resolve(1));
  });
  clearTimeout(timer);
  clearInterval(earlyDone);

  return { exitCode, timedOut, killedAfterWrite, stdout, stderr };
}

function saveState(stateFile, state) {
  fs.writeFileSync(stateFile, JSON.stringify(state, null, 2), 'utf8');
}

const articles = readJson(linksFile);
fs.mkdirSync(outDir, { recursive: true });

const stateFile = DEFAULT_STATE;
let state = { ok: {}, failed: {}, updatedAt: null };
if (fs.existsSync(stateFile)) {
  state = { ...state, ...readJson(stateFile) };
}

const todo = Number.isFinite(limit) ? articles.slice(0, limit) : articles;
console.log(`Loaded ${articles.length} article links; processing ${todo.length}`);
console.log(`Output: ${outDir}`);
console.log(`Pacing: delay=${noDelay ? 'off' : `${fmtDuration(delayMinMs)}-${fmtDuration(delayMaxMs)}`}, batchSize=${batchSize}, rest=${fmtDuration(restMs)}`);

let ok = 0;
let skipped = 0;
let failed = 0;
let fetchedInBatch = 0;

for (let i = 0; i < todo.length; i++) {
  const article = todo[i];
  const outputFile = path.join(outDir, `${article.date}.md`);

  if (!force && isGoodMarkdown(outputFile, article.date)) {
    skipped++;
    state.ok[article.date] = { url: article.link, file: path.relative(ROOT, outputFile), skipped: true };
    delete state.failed[article.date];
    console.log(`[${i + 1}/${todo.length}] SKIP ${article.date}`);
    state.updatedAt = new Date().toISOString();
    saveState(stateFile, state);
    continue;
  }

  console.log(`[${i + 1}/${todo.length}] FETCH ${article.date}`);
  const result = await runBaoyu(article, outputFile);
  const good = isGoodMarkdown(outputFile, article.date);

  if (good) {
    ok++;
    fetchedInBatch++;
    state.ok[article.date] = {
      url: article.link,
      file: path.relative(ROOT, outputFile),
      timedOut: result.timedOut,
      killedAfterWrite: result.killedAfterWrite,
      exitCode: result.exitCode,
      bytes: fs.statSync(outputFile).size,
    };
    delete state.failed[article.date];
    console.log(`  OK ${article.date} bytes=${fs.statSync(outputFile).size}${result.killedAfterWrite ? ' killedAfterWrite' : ''}${result.timedOut ? ' timedOutAfterWrite' : ''}`);
  } else {
    failed++;
    fetchedInBatch++;
    state.failed[article.date] = {
      url: article.link,
      file: path.relative(ROOT, outputFile),
      timedOut: result.timedOut,
      exitCode: result.exitCode,
      stderr: result.stderr.slice(-1200),
    };
    console.log(`  FAIL ${article.date} exit=${result.exitCode}${result.timedOut ? ' timeout' : ''}`);
  }

  state.updatedAt = new Date().toISOString();
  saveState(stateFile, state);

  if (Number.isFinite(maxFetch) && fetchedInBatch >= maxFetch) {
    console.log(`Reached --max-fetch ${maxFetch}; stopping this run`);
    break;
  }

  if (fetchedInBatch > 0 && fetchedInBatch % batchSize === 0 && i < todo.length - 1 && !noDelay) {
    console.log(`  Batch rest ${fmtDuration(restMs)} after ${fetchedInBatch} fetched attempts`);
    await sleep(restMs);
  } else if (fetchedInBatch > 0 && i < todo.length - 1) {
    const waitMs = randomDelay();
    if (waitMs > 0) {
      console.log(`  Waiting ${fmtDuration(waitMs)} before next article`);
      await sleep(waitMs);
    }
  }
}

state.updatedAt = new Date().toISOString();
saveState(stateFile, state);
console.log(`Done. ok=${ok} skipped=${skipped} failed=${failed}`);
