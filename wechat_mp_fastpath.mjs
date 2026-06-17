#!/usr/bin/env node
// Fast path for WeChat Official Account articles.
//
// This intentionally does not use baoyu-fetch/Defuddle. It talks to an
// existing Chrome DevTools endpoint, reads the WeChat article DOM directly, and
// saves #js_content as Markdown with embedded HTML tables/images.

import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const SOURCE_DIR = path.join(ROOT, 'sources', 'jinri-jiujia-wechat-links');

const DEFAULT_CDP_URL = (process.env.WECHAT_CDP_URL || process.env.BAOYU_CDP_URL || 'http://127.0.0.1:9223').replace(/\/$/, '');
const DEFAULT_EXPECTED_AUTHOR = process.env.WECHAT_EXPECTED_AUTHOR ?? '\u4eca\u65e5\u9152\u4ef7';

const options = {
  cdpUrl: DEFAULT_CDP_URL,
  linksFile: path.join(SOURCE_DIR, '2025-links.json'),
  outDir: '',
  stateFile: '',
  url: '',
  date: '',
  limit: null,
  maxFetch: null,
  force: false,
  strictDate: true,
  requireTable: true,
  expectedAuthor: DEFAULT_EXPECTED_AUTHOR,
  commandTimeoutMs: Number(process.env.WECHAT_CDP_COMMAND_TIMEOUT_MS || 12_000),
  pageTimeoutMs: Number(process.env.WECHAT_PAGE_TIMEOUT_MS || 90_000),
  minBytes: Number(process.env.WECHAT_MIN_GOOD_BYTES || 3_000),
  minTables: Number(process.env.WECHAT_MIN_TABLES || 30),
  minRows: Number(process.env.WECHAT_MIN_ROWS || 300),
  stablePolls: Number(process.env.WECHAT_STABLE_POLLS || 3),
  pollIntervalMs: Number(process.env.WECHAT_POLL_INTERVAL_MS || 1_000),
  delayMinMs: Number(process.env.WECHAT_DELAY_MIN_MS || 5_000),
  delayMaxMs: Number(process.env.WECHAT_DELAY_MAX_MS || 10_000),
  batchSize: Number(process.env.WECHAT_BATCH_SIZE || 8),
  restMs: Number(process.env.WECHAT_BATCH_REST_MS || 60_000),
  noDelay: false,
};

function usage() {
  return `Usage:
  node wechat_mp_fastpath.mjs --links sources/jinri-jiujia-wechat-links/2025-links.json
  node wechat_mp_fastpath.mjs --url https://mp.weixin.qq.com/s/... --date 2025-09-23

Options:
  --cdp-url <url>              Chrome CDP endpoint. Default: ${DEFAULT_CDP_URL}
  --links <file>               JSON or CSV records with date + link/url
  --url <url>                  Fetch one URL instead of a links file
  --date <YYYY-MM-DD>          Limit links file to one date, or date for --url
  --out-dir <dir>              Output directory. Default: YEAR-md next to links file
  --state <file>               State JSON path. Default: YEAR-md-fastpath-state.json
  --max-fetch <n>              Stop after n attempted fetches
  --limit <n>                  Only consider first n records
  --force                      Re-fetch even if output already passes quality check
  --expected-author <name>     Validate account name. Default: ${DEFAULT_EXPECTED_AUTHOR}
  --no-author-check            Disable account-name validation
  --no-strict-date             Do not fail on publish-date mismatch
  --allow-no-table             Do not require at least one HTML table
  --min-tables <n>             Required table count before saving. Default: 30
  --min-rows <n>               Required tr count before saving. Default: 300
  --stable-polls <n>           Consecutive stable polls before saving. Default: 3
  --delay-min-ms <n>           Per-article delay lower bound. Default: 5000
  --delay-max-ms <n>           Per-article delay upper bound. Default: 10000
  --batch-size <n>             Rest after this many fetched attempts. Default: 8
  --rest-ms <n>                Batch rest. Default: 60000
  --no-delay                   Disable pacing
`;
}

const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i += 1) {
  const arg = argv[i];
  if (arg === '--help' || arg === '-h') {
    console.log(usage());
    process.exit(0);
  } else if (arg === '--cdp-url') {
    options.cdpUrl = argv[++i].replace(/\/$/, '');
  } else if (arg === '--links') {
    options.linksFile = path.resolve(argv[++i]);
  } else if (arg === '--url') {
    options.url = argv[++i];
  } else if (arg === '--date') {
    options.date = argv[++i];
  } else if (arg === '--out-dir') {
    options.outDir = path.resolve(argv[++i]);
  } else if (arg === '--state') {
    options.stateFile = path.resolve(argv[++i]);
  } else if (arg === '--limit') {
    options.limit = Number(argv[++i]);
  } else if (arg === '--max-fetch') {
    options.maxFetch = Number(argv[++i]);
  } else if (arg === '--force') {
    options.force = true;
  } else if (arg === '--expected-author') {
    options.expectedAuthor = argv[++i];
  } else if (arg === '--no-author-check') {
    options.expectedAuthor = '';
  } else if (arg === '--no-strict-date') {
    options.strictDate = false;
  } else if (arg === '--allow-no-table') {
    options.requireTable = false;
  } else if (arg === '--command-timeout-ms') {
    options.commandTimeoutMs = Number(argv[++i]);
  } else if (arg === '--page-timeout-ms') {
    options.pageTimeoutMs = Number(argv[++i]);
  } else if (arg === '--min-bytes') {
    options.minBytes = Number(argv[++i]);
  } else if (arg === '--min-tables') {
    options.minTables = Number(argv[++i]);
  } else if (arg === '--min-rows') {
    options.minRows = Number(argv[++i]);
  } else if (arg === '--stable-polls') {
    options.stablePolls = Number(argv[++i]);
  } else if (arg === '--poll-interval-ms') {
    options.pollIntervalMs = Number(argv[++i]);
  } else if (arg === '--delay-min-ms') {
    options.delayMinMs = Number(argv[++i]);
  } else if (arg === '--delay-max-ms') {
    options.delayMaxMs = Number(argv[++i]);
  } else if (arg === '--batch-size') {
    options.batchSize = Number(argv[++i]);
  } else if (arg === '--rest-ms') {
    options.restMs = Number(argv[++i]);
  } else if (arg === '--no-delay') {
    options.noDelay = true;
  } else {
    throw new Error(`Unknown argument: ${arg}\n\n${usage()}`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function withTimeout(promise, ms, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function randomDelayMs() {
  if (options.noDelay) return 0;
  const min = Math.max(0, Math.min(options.delayMinMs, options.delayMaxMs));
  const max = Math.max(min, options.delayMaxMs);
  return min + Math.floor(Math.random() * (max - min + 1));
}

function fmtMs(ms) {
  const seconds = Math.round(ms / 1000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m${String(seconds % 60).padStart(2, '0')}s`;
}

function readJsonMaybeDoubleEncoded(file) {
  const raw = fs.readFileSync(file, 'utf8');
  const parsed = JSON.parse(raw);
  return typeof parsed === 'string' ? JSON.parse(parsed) : parsed;
}

function parseCsvLine(line) {
  const values = [];
  let value = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"' && quoted && line[i + 1] === '"') {
      value += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === ',' && !quoted) {
      values.push(value);
      value = '';
    } else {
      value += char;
    }
  }
  values.push(value);
  return values;
}

function readCsv(file) {
  const lines = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return [];
  const headers = parseCsvLine(lines[0]).map(header => header.trim());
  return lines.slice(1).map(line => {
    const values = parseCsvLine(line);
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? '';
    });
    return normalizeRecord(row);
  });
}

function normalizeRecord(record) {
  const date = String(record.date || record.publishDate || options.date || '').trim();
  const link = String(record.link || record.url || record.href || options.url || '').trim();
  const title = String(record.title || '').trim();
  if (!link) {
    throw new Error(`Record is missing link/url: ${JSON.stringify(record)}`);
  }
  return { ...record, date, link, title };
}

function loadRecords() {
  if (options.url) {
    return [normalizeRecord({ date: options.date, link: options.url })];
  }

  const ext = path.extname(options.linksFile).toLowerCase();
  const records = ext === '.csv'
    ? readCsv(options.linksFile)
    : readJsonMaybeDoubleEncoded(options.linksFile).map(normalizeRecord);
  return records;
}

function inferYearFromPathOrRecords(records) {
  const fromFile = path.basename(options.linksFile).match(/(\d{4})-links\.(?:json|csv)$/i)?.[1];
  if (fromFile) return fromFile;
  return records.find(record => /^\d{4}-\d{2}-\d{2}$/.test(record.date))?.date.slice(0, 4) || 'wechat';
}

function ensureDerivedPaths(records) {
  const year = inferYearFromPathOrRecords(records);
  if (!options.outDir) {
    options.outDir = path.join(path.dirname(options.linksFile), `${year}-md`);
  }
  if (!options.stateFile) {
    options.stateFile = path.join(path.dirname(options.linksFile), `${year}-md-fastpath-state.json`);
  }
}

function dateTextToIso(text) {
  const normalized = String(text || '').trim();
  let match = normalized.match(/(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})/);
  if (!match) {
    match = normalized.match(/(\d{4})\s*\u5e74\s*(\d{1,2})\s*\u6708\s*(\d{1,2})\s*\u65e5/);
  }
  if (!match) return '';
  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
}

function chineseDate(date) {
  const match = String(date || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return '';
  return `${match[1]}\u5e74${Number(match[2])}\u6708${Number(match[3])}\u65e5`;
}

function yamlString(value) {
  return JSON.stringify(String(value ?? ''));
}

function safeFilename(record, index) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(record.date)) return `${record.date}.md`;
  const id = record.msgid || record.link.split('/').filter(Boolean).pop() || `article-${index + 1}`;
  return `${String(id).replace(/[^a-zA-Z0-9_-]+/g, '-').slice(0, 80)}.md`;
}

function outputFileFor(record, index) {
  return path.join(options.outDir, safeFilename(record, index));
}

function isGoodMarkdown(file, record) {
  if (!fs.existsSync(file)) return false;
  const stat = fs.statSync(file);
  if (stat.size < options.minBytes) return false;
  const markdown = fs.readFileSync(file, 'utf8');
  if (!markdown.includes('adapter: "wechat-mp-fastpath"')) return false;
  if (options.requireTable) {
    const tableCount = (markdown.match(/<table\b/gi) || []).length;
    const rowCount = (markdown.match(/<tr\b/gi) || []).length;
    if (tableCount < options.minTables || rowCount < options.minRows) {
      return false;
    }
  }
  if (record.date && options.strictDate) {
    return markdown.includes(`publishDate: ${yamlString(record.date)}`) ||
      markdown.includes(record.date) ||
      markdown.includes(chineseDate(record.date));
  }
  return true;
}

function buildMarkdown(record, page) {
  const capturedAt = new Date().toISOString();
  const title = page.title || record.title || `WeChat article ${record.date || ''}`.trim();
  return [
    '---',
    `title: ${yamlString(title)}`,
    `url: ${yamlString(page.url || record.link)}`,
    `requestedUrl: ${yamlString(record.link)}`,
    `accountName: ${yamlString(page.accountName)}`,
    `publishTime: ${yamlString(page.publishTime)}`,
    `publishDate: ${yamlString(page.publishDate)}`,
    `coverImage: ${yamlString(page.coverImage)}`,
    `summary: ${yamlString(page.summary)}`,
    'siteName: "WeChat Official Account"',
    'adapter: "wechat-mp-fastpath"',
    `capturedAt: ${yamlString(capturedAt)}`,
    `tableCount: ${Number(page.tableCount || 0)}`,
    `rowCount: ${Number(page.rowCount || 0)}`,
    `imageCount: ${Number(page.imageCount || 0)}`,
    'kind: "wechat/article"',
    '---',
    '',
    `# ${title}`,
    '',
    page.contentHtml || '',
    '',
  ].join('\n');
}

async function cdpFetchJson(endpoint, init = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.commandTimeoutMs);
  try {
    const response = await fetch(`${options.cdpUrl}${endpoint}`, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw new Error(`${endpoint} failed: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function createTarget(url) {
  return cdpFetchJson(`/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
}

async function closeTarget(id) {
  if (!id) return;
  try {
    await cdpFetchJson(`/json/close/${encodeURIComponent(id)}`);
  } catch {
    // Best-effort cleanup.
  }
}

class CdpPage {
  constructor(webSocketDebuggerUrl) {
    this.webSocketDebuggerUrl = webSocketDebuggerUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  async open() {
    this.ws = new WebSocket(this.webSocketDebuggerUrl);
    this.ws.addEventListener('message', event => this.handleMessage(String(event.data)));
    await withTimeout(new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    }), options.commandTimeoutMs, 'CDP websocket open');
  }

  handleMessage(raw) {
    const message = JSON.parse(raw);
    if (typeof message.id !== 'number') return;
    const pending = this.pending.get(message.id);
    if (!pending) return;
    this.pending.delete(message.id);
    clearTimeout(pending.timer);
    if (message.error) {
      pending.reject(new Error(`${pending.method}: ${message.error.message || 'CDP error'}`));
    } else {
      pending.resolve(message.result ?? {});
    }
  }

  send(method, params = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('CDP websocket is not open');
    }
    const id = this.nextId;
    this.nextId += 1;
    const payload = { id, method, params };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out after ${options.commandTimeoutMs}ms`));
      }, options.commandTimeoutMs);
      this.pending.set(id, { resolve, reject, timer, method });
      this.ws.send(JSON.stringify(payload));
    });
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text || 'Runtime.evaluate exception');
    }
    return result.result?.value;
  }

  close() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.close();
    }
  }
}

const EXTRACT_SCRIPT = String.raw`
(() => {
  const meta = (...names) => {
    for (const name of names) {
      const el = document.querySelector('meta[property="' + name + '"], meta[name="' + name + '"]');
      const value = el && el.getAttribute('content');
      if (value && value.trim()) return value.trim();
    }
    return '';
  };

  const abs = value => {
    if (!value) return value;
    try {
      return new URL(value, document.baseURI || location.href).href;
    } catch {
      return value;
    }
  };

  const clean = root => {
    const clone = root.cloneNode(true);
    clone.querySelectorAll('script,style,iframe,noscript,template,svg,path,mp-common-widget').forEach(el => el.remove());
    clone.querySelectorAll('*').forEach(el => {
      const tag = el.tagName.toLowerCase();
      if (tag === 'img') {
        const dataSrc = el.getAttribute('data-src') || el.getAttribute('data-original');
        const src = el.getAttribute('src');
        if (dataSrc && (!src || src.startsWith('data:'))) el.setAttribute('src', dataSrc);
        if (el.getAttribute('src')) el.setAttribute('src', abs(el.getAttribute('src')));
        if (!el.getAttribute('alt')) el.setAttribute('alt', 'image');
      }
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name.toLowerCase();
        if (name.startsWith('on') || name.startsWith('aria-')) {
          el.removeAttribute(attr.name);
        } else if (['style', 'class', 'id', 'data-src', 'data-original', 'data-ratio', 'data-w'].includes(name)) {
          el.removeAttribute(attr.name);
        } else if ((name === 'href' || name === 'src' || name === 'poster') && attr.value) {
          el.setAttribute(attr.name, abs(attr.value));
        }
      }
    });
    return clone.innerHTML.trim();
  };

  const content = document.querySelector('#js_content');
  const contentHtml = content ? clean(content) : '';
  const publishTime = (document.querySelector('#publish_time')?.textContent || '').trim();
  const title = (document.querySelector('#activity-name')?.textContent || '').trim() ||
    meta('og:title') ||
    document.title ||
    '';
  const accountName = (document.querySelector('#js_name')?.textContent || '').trim() || meta('author');
  const text = content ? content.innerText.replace(/\s+/g, ' ').trim() : '';
  return {
    readyState: document.readyState,
    url: location.href,
    title,
    accountName,
    publishTime,
    summary: meta('description', 'og:description'),
    coverImage: meta('og:image'),
    contentHtml,
    textLength: text.length,
    textSample: text.slice(0, 300),
    tableCount: (contentHtml.match(/<table\b/gi) || []).length,
    rowCount: (contentHtml.match(/<tr\b/gi) || []).length,
    imageCount: (contentHtml.match(/<img\b/gi) || []).length
  };
})()
`;

async function waitForArticle(page) {
  const started = Date.now();
  let last = null;
  let stableCount = 0;
  let lastSignature = '';
  while (Date.now() - started < options.pageTimeoutMs) {
    last = await page.evaluate(EXTRACT_SCRIPT);
    const hasContent = last?.contentHtml && last.textLength > 100;
    const tableCount = Number(last?.tableCount || 0);
    const rowCount = Number(last?.rowCount || 0);
    const hasRequiredTable = !options.requireTable ||
      (tableCount >= options.minTables && rowCount >= options.minRows);
    const signature = `${tableCount}:${rowCount}:${last?.textLength || 0}`;
    if (hasContent && hasRequiredTable && signature === lastSignature) {
      stableCount += 1;
    } else {
      stableCount = hasContent && hasRequiredTable ? 1 : 0;
      lastSignature = signature;
    }
    if (hasContent && hasRequiredTable && stableCount >= options.stablePolls) {
      return last;
    }
    await sleep(options.pollIntervalMs);
  }
  const detail = last ? `title=${last.title || ''} tables=${last.tableCount || 0} rows=${last.rowCount || 0} text=${last.textLength || 0} sample=${last.textSample || ''}` : 'no page data';
  throw new Error(`timed out waiting for #js_content: ${detail.slice(0, 500)}`);
}

function validateArticle(record, page) {
  page.publishDate = dateTextToIso(page.publishTime);
  if (options.expectedAuthor && page.accountName && page.accountName !== options.expectedAuthor) {
    throw new Error(`account mismatch: expected ${options.expectedAuthor}, got ${page.accountName}`);
  }
  if (record.date && options.strictDate && page.publishDate !== record.date) {
    throw new Error(`publish date mismatch: expected ${record.date}, got ${page.publishDate || page.publishTime || 'empty'}`);
  }
  if (options.requireTable) {
    const tableCount = Number(page.tableCount || 0);
    const rowCount = Number(page.rowCount || 0);
    if (tableCount < options.minTables || rowCount < options.minRows) {
      throw new Error(`incomplete article tables: tables=${tableCount}/${options.minTables}, rows=${rowCount}/${options.minRows}`);
    }
  }
}

async function fetchOne(record, outputFile) {
  const target = await createTarget(record.link);
  const page = new CdpPage(target.webSocketDebuggerUrl);
  try {
    await page.open();
    await page.send('Runtime.enable');
    await page.send('Page.enable').catch(() => {});
    const article = await waitForArticle(page);
    validateArticle(record, article);
    fs.mkdirSync(path.dirname(outputFile), { recursive: true });
    fs.writeFileSync(outputFile, buildMarkdown(record, article), 'utf8');
    if (!isGoodMarkdown(outputFile, record)) {
      throw new Error(`saved markdown failed quality check; bytes=${fs.statSync(outputFile).size}`);
    }
    return {
      bytes: fs.statSync(outputFile).size,
      title: article.title,
      accountName: article.accountName,
      publishDate: article.publishDate,
      publishTime: article.publishTime,
      tableCount: article.tableCount,
      rowCount: article.rowCount,
      imageCount: article.imageCount,
      finalUrl: article.url,
    };
  } finally {
    page.close();
    await closeTarget(target.id);
  }
}

function loadState() {
  if (!fs.existsSync(options.stateFile)) {
    return { ok: {}, failed: {}, updatedAt: null };
  }
  return { ok: {}, failed: {}, ...readJsonMaybeDoubleEncoded(options.stateFile) };
}

function saveState(state) {
  fs.mkdirSync(path.dirname(options.stateFile), { recursive: true });
  fs.writeFileSync(options.stateFile, JSON.stringify({ ...state, updatedAt: new Date().toISOString() }, null, 2), 'utf8');
}

let records = loadRecords();
ensureDerivedPaths(records);
if (Number.isFinite(options.limit)) {
  records = records.slice(0, options.limit);
}
if (options.date && !options.url) {
  records = records.filter(record => record.date === options.date);
  if (records.length === 0) {
    throw new Error(`No record found for --date ${options.date}`);
  }
}

fs.mkdirSync(options.outDir, { recursive: true });
const state = loadState();

console.log(`Loaded ${records.length} record(s)`);
console.log(`CDP: ${options.cdpUrl}`);
console.log(`Output: ${options.outDir}`);
console.log(`State: ${options.stateFile}`);
console.log(`Pacing: ${options.noDelay ? 'off' : `${fmtMs(options.delayMinMs)}-${fmtMs(options.delayMaxMs)}, batch ${options.batchSize}, rest ${fmtMs(options.restMs)}`}`);
console.log(`Quality gate: tables>=${options.minTables}, rows>=${options.minRows}, stablePolls=${options.stablePolls}`);

let ok = 0;
let skipped = 0;
let failed = 0;
let attempted = 0;

for (let i = 0; i < records.length; i += 1) {
  const record = records[i];
  const outputFile = outputFileFor(record, i);
  const label = record.date || record.link;

  if (!options.force && isGoodMarkdown(outputFile, record)) {
    skipped += 1;
    state.ok[label] = {
      url: record.link,
      file: path.relative(ROOT, outputFile),
      skipped: true,
      adapter: 'wechat-mp-fastpath',
    };
    delete state.failed[label];
    saveState(state);
    console.log(`[${i + 1}/${records.length}] SKIP ${label}`);
    continue;
  }

  console.log(`[${i + 1}/${records.length}] FETCH ${label}`);
  attempted += 1;
  try {
    const result = await fetchOne(record, outputFile);
    ok += 1;
    state.ok[label] = {
      url: record.link,
      file: path.relative(ROOT, outputFile),
      adapter: 'wechat-mp-fastpath',
      ...result,
    };
    delete state.failed[label];
    console.log(`  OK bytes=${result.bytes} tables=${result.tableCount} rows=${result.rowCount} publishDate=${result.publishDate || ''}`);
  } catch (error) {
    failed += 1;
    state.failed[label] = {
      url: record.link,
      file: path.relative(ROOT, outputFile),
      adapter: 'wechat-mp-fastpath',
      error: String(error?.message || error).slice(-1200),
    };
    console.log(`  FAIL ${String(error?.message || error)}`);
  }
  saveState(state);

  if (Number.isFinite(options.maxFetch) && attempted >= options.maxFetch) {
    console.log(`Reached --max-fetch ${options.maxFetch}; stopping`);
    break;
  }

  if (i < records.length - 1 && attempted > 0) {
    if (!options.noDelay && options.batchSize > 0 && attempted % options.batchSize === 0) {
      console.log(`  Batch rest ${fmtMs(options.restMs)}`);
      await sleep(options.restMs);
    } else {
      const wait = randomDelayMs();
      if (wait > 0) {
        console.log(`  Waiting ${fmtMs(wait)}`);
        await sleep(wait);
      }
    }
  }
}

saveState(state);
console.log(`Done. ok=${ok} skipped=${skipped} failed=${failed}`);
