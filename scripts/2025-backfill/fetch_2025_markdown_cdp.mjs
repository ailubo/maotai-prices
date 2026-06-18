// Fetch verified 2025 今日酒价 WeChat article URLs through an existing Chrome CDP
// session and save #js_content HTML in the same markdown directory used by the
// extractor. This avoids baoyu-fetch generic adapter stalls on long WeChat pages.

import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const DEFAULT_LINKS = path.join(ROOT, 'sources/jinri-jiujia-wechat-links/2025-links.json');
const DEFAULT_OUT_DIR = path.join(ROOT, 'sources/jinri-jiujia-wechat-links/2025-md');
const DEFAULT_STATE = path.join(ROOT, 'sources/jinri-jiujia-wechat-links/2025-md-state.json');

const CDP_URL = (process.env.BAOYU_CDP_URL || 'http://127.0.0.1:9223').replace(/\/$/, '');
const MIN_GOOD_BYTES = Number(process.env.BAOYU_MIN_GOOD_BYTES || 8_000);
const WAIT_TIMEOUT_MS = Number(process.env.CDP_FETCH_TIMEOUT_MS || 45_000);

const argv = process.argv.slice(2);
let limit = null;
let maxFetch = null;
let force = false;
let linksFile = DEFAULT_LINKS;
let outDir = DEFAULT_OUT_DIR;
let delayMs = Number(process.env.CDP_FETCH_DELAY_MS || 3_000);
let noDelay = false;
let onlyDate = null;

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
  } else if (arg === '--delay-ms') {
    delayMs = Number(argv[++i]);
  } else if (arg === '--no-delay') {
    noDelay = true;
  } else if (arg === '--date') {
    onlyDate = argv[++i];
  } else {
    throw new Error(`Unknown argument: ${arg}`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function readJson(file) {
  const raw = fs.readFileSync(file, 'utf8');
  const parsed = JSON.parse(raw);
  return typeof parsed === 'string' ? JSON.parse(parsed) : parsed;
}

function chineseDate(expectedDate) {
  return expectedDate.replace(/^(\d{4})-(\d{2})-(\d{2})$/, (_, y, m, d) => {
    return `${y}年${Number(m)}月${Number(d)}日`;
  });
}

function isGoodMarkdown(file, expectedDate) {
  if (!fs.existsSync(file)) return false;
  const stat = fs.statSync(file);
  if (stat.size < MIN_GOOD_BYTES) return false;
  const md = fs.readFileSync(file, 'utf8');
  return md.includes('今日酒价') && md.includes('<table') && (
    md.includes(expectedDate) || md.includes(chineseDate(expectedDate))
  );
}

function cleanHtmlScript() {
  return String.raw`function cleanArticleHtml(root) {
    const clone = root.cloneNode(true);
    clone.querySelectorAll('script,style,iframe,noscript,template,svg,path').forEach(el => el.remove());
    clone.querySelectorAll('*').forEach(el => {
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name.toLowerCase();
        if (
          name === 'style' ||
          name === 'class' ||
          name === 'id' ||
          name === 'width' ||
          name === 'height' ||
          name === '_width' ||
          name === '_height'
        ) {
          el.removeAttribute(attr.name);
          continue;
        }
        if (name.startsWith('aria-') || name.startsWith('on')) {
          el.removeAttribute(attr.name);
          continue;
        }
        if (name === 'src' && el.tagName.toLowerCase() === 'img' && !attr.value) {
          el.removeAttribute(attr.name);
        }
      }
      if (el.tagName.toLowerCase() === 'img') {
        const dataSrc = el.getAttribute('data-src');
        if (dataSrc && !el.getAttribute('src')) {
          el.setAttribute('src', dataSrc);
        }
        if (!el.getAttribute('alt')) {
          el.setAttribute('alt', '图片');
        }
      }
    });
    return clone.innerHTML;
  }`;
}

function saveState(stateFile, state) {
  fs.writeFileSync(stateFile, JSON.stringify(state, null, 2), 'utf8');
}

function yamlString(value) {
  return JSON.stringify(String(value || ''));
}

async function cdpJson(endpoint, init) {
  const response = await fetch(`${CDP_URL}${endpoint}`, init);
  if (!response.ok) {
    throw new Error(`${endpoint} failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function createTarget(url) {
  return cdpJson(`/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
}

async function closeTarget(id) {
  try {
    await fetch(`${CDP_URL}/json/close/${id}`);
  } catch {
    // Best-effort cleanup only.
  }
}

class CdpClient {
  constructor(webSocketDebuggerUrl) {
    this.ws = new WebSocket(webSocketDebuggerUrl);
    this.nextId = 0;
    this.pending = new Map();
    this.ws.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        this.pending.get(message.id)(message);
        this.pending.delete(message.id);
      }
    };
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
  }

  send(method, params = {}) {
    const id = ++this.nextId;
    const message = { id, method, params };
    const promise = new Promise(resolve => this.pending.set(id, resolve));
    this.ws.send(JSON.stringify(message));
    return promise;
  }

  close() {
    this.ws.close();
  }
}

async function evaluatePage(client) {
  const expression = `(() => {
    ${cleanHtmlScript()}
    const content = document.querySelector('#js_content');
    const text = content?.innerText || '';
    const meta = name => document.querySelector('meta[property="' + name + '"], meta[name="' + name + '"]')?.content || '';
    const activityTitle = document.querySelector('#activity-name')?.textContent?.trim() || '';
    const contentHtml = content ? cleanArticleHtml(content) : '';
    return {
      title: activityTitle || meta('og:title') || document.title,
      url: location.href,
      author: document.querySelector('#js_name')?.textContent?.trim() || meta('author'),
      publishTime: document.querySelector('#publish_time')?.textContent?.trim() || '',
      summary: meta('description') || meta('og:description'),
      coverImage: meta('og:image'),
      contentHtml,
      tableCount: (contentHtml.match(/<table/gi) || []).length,
      textSample: text.slice(0, 300),
    };
  })()`;
  const result = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.error) {
    throw new Error(result.error.message || 'Runtime.evaluate failed');
  }
  if (result.result.exceptionDetails) {
    throw new Error(result.result.exceptionDetails.text || 'page evaluation failed');
  }
  return result.result.result.value;
}

async function waitForArticle(client, expectedDate) {
  const started = Date.now();
  let last = null;
  while (Date.now() - started < WAIT_TIMEOUT_MS) {
    last = await evaluatePage(client);
    const hasDate = (last.contentHtml || '').includes(chineseDate(expectedDate)) ||
      (last.contentHtml || '').includes(expectedDate);
    const hasUsefulTitle = last.title && last.title !== '微信公众平台';
    if (last.tableCount > 0 && hasDate && (hasUsefulTitle || Date.now() - started > 8_000)) {
      return last;
    }
    await sleep(1_000);
  }
  const detail = last ? `title=${last.title || ''} tables=${last.tableCount || 0} sample=${last.textSample || ''}` : 'no page data';
  throw new Error(`timed out waiting for article content: ${detail.slice(0, 500)}`);
}

function buildMarkdown(article, page) {
  const capturedAt = new Date().toISOString();
  const title = page.title || `今日酒价 ${article.date}`;
  return [
    '---',
    `title: ${yamlString(title)}`,
    `url: ${yamlString(page.url || article.link)}`,
    `requestedUrl: ${yamlString(article.link)}`,
    `author: ${yamlString(page.author || '今日酒价')}`,
    `coverImage: ${yamlString(page.coverImage || '')}`,
    'siteName: "微信公众平台"',
    `summary: ${yamlString(page.summary || '')}`,
    'adapter: "cdp-js-content"',
    `capturedAt: ${yamlString(capturedAt)}`,
    `publishTime: ${yamlString(page.publishTime || '')}`,
    'kind: "generic/article"',
    '---',
    '',
    `# ${title}`,
    '',
    page.contentHtml || '',
    '',
  ].join('\n');
}

async function fetchArticle(article, outputFile) {
  const target = await createTarget(article.link);
  const client = new CdpClient(target.webSocketDebuggerUrl);
  try {
    await client.open();
    await client.send('Page.enable');
    await sleep(1_500);
    const page = await waitForArticle(client, article.date);
    fs.mkdirSync(path.dirname(outputFile), { recursive: true });
    fs.writeFileSync(outputFile, buildMarkdown(article, page), 'utf8');
    return {
      ok: isGoodMarkdown(outputFile, article.date),
      bytes: fs.existsSync(outputFile) ? fs.statSync(outputFile).size : 0,
      title: page.title,
      publishTime: page.publishTime,
      tableCount: page.tableCount,
    };
  } finally {
    client.close();
    await closeTarget(target.id);
  }
}

const articles = readJson(linksFile);
fs.mkdirSync(outDir, { recursive: true });

const stateFile = DEFAULT_STATE;
let state = { ok: {}, failed: {}, updatedAt: null };
if (fs.existsSync(stateFile)) {
  state = { ...state, ...readJson(stateFile) };
}

let todo = Number.isFinite(limit) ? articles.slice(0, limit) : articles;
if (onlyDate) {
  todo = todo.filter(article => article.date === onlyDate);
  if (todo.length === 0) {
    throw new Error(`No article found for --date ${onlyDate}`);
  }
}
console.log(`Loaded ${articles.length} article links; processing ${todo.length}`);
console.log(`CDP: ${CDP_URL}`);
console.log(`Output: ${outDir}`);

let ok = 0;
let skipped = 0;
let failed = 0;
let fetched = 0;

for (let i = 0; i < todo.length; i++) {
  const article = todo[i];
  const outputFile = path.join(outDir, `${article.date}.md`);

  if (!force && isGoodMarkdown(outputFile, article.date)) {
    skipped++;
    state.ok[article.date] = { url: article.link, file: path.relative(ROOT, outputFile), skipped: true };
    delete state.failed[article.date];
    state.updatedAt = new Date().toISOString();
    saveState(stateFile, state);
    continue;
  }

  console.log(`[${i + 1}/${todo.length}] FETCH ${article.date} ${article.link}`);
  try {
    const result = await fetchArticle(article, outputFile);
    fetched++;
    if (!result.ok) {
      throw new Error(`saved markdown did not pass quality check; bytes=${result.bytes}`);
    }
    ok++;
    state.ok[article.date] = {
      url: article.link,
      file: path.relative(ROOT, outputFile),
      bytes: result.bytes,
      title: result.title,
      publishTime: result.publishTime,
      tableCount: result.tableCount,
      adapter: 'cdp-js-content',
    };
    delete state.failed[article.date];
    console.log(`  OK ${article.date} bytes=${result.bytes} tables=${result.tableCount}`);
  } catch (error) {
    failed++;
    fetched++;
    state.failed[article.date] = {
      url: article.link,
      file: path.relative(ROOT, outputFile),
      error: String(error?.message || error).slice(-1200),
      adapter: 'cdp-js-content',
    };
    console.log(`  FAIL ${article.date} ${String(error?.message || error)}`);
  }

  state.updatedAt = new Date().toISOString();
  saveState(stateFile, state);

  if (Number.isFinite(maxFetch) && fetched >= maxFetch) {
    console.log(`Reached --max-fetch ${maxFetch}; stopping this run`);
    break;
  }

  if (!noDelay && delayMs > 0 && i < todo.length - 1) {
    await sleep(delayMs);
  }
}

state.updatedAt = new Date().toISOString();
saveState(stateFile, state);
console.log(`Done. ok=${ok} skipped=${skipped} failed=${failed}`);
