#!/usr/bin/env node
/**
 * Fetch a single WeChat article body with Playwright and save as markdown-ish file.
 * Usage: node fetch_article_playwright.cjs <url> <output.md>
 * Exit codes: 0 = success; 1 = failure; 75 = another instance running.
 * Hardening (2026-08-12): no process.exit in try/catch; PID-aware lock; strict cleanup.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const url = process.argv[2];
const output = process.argv[3];
if (!url || !output) {
  console.error('用法: node fetch_article_playwright.cjs <url> <output.md>');
  process.exitCode = 2;
} else {
  main();
}

const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PROXY = process.env.MAOTAI_PROXY || 'http://127.0.0.1:7897';
const LOCK_FILE = '/tmp/maotai-playwright.lock';
const LOCK_STALE_MS = 10 * 60 * 1000;

let lockAcquired = false;
let browser = null;

function acquireLock() {
  try {
    fs.writeFileSync(LOCK_FILE, `${process.pid} ${Date.now()}`, { flag: 'wx' });
    lockAcquired = true;
    return true;
  } catch (e) {
    try {
      const [pid, ts] = fs.readFileSync(LOCK_FILE, 'utf-8').trim().split(/\s+/);
      const pidNum = parseInt(pid, 10);
      const tsNum = parseInt(ts, 10);
      const dead = !pidNum || (() => { try { process.kill(pidNum, 0); return false; } catch (err) { return err.code === 'ESRCH'; } })();
      const old = !tsNum || (Date.now() - tsNum) > LOCK_STALE_MS;
      if (dead || old) {
        fs.unlinkSync(LOCK_FILE);
        try {
          fs.writeFileSync(LOCK_FILE, `${process.pid} ${Date.now()}`, { flag: 'wx' });
          lockAcquired = true;
          return true;
        } catch (e2) { return false; }
      }
    } catch (e2) {
      try { fs.unlinkSync(LOCK_FILE); } catch (e3) {}
      try {
        fs.writeFileSync(LOCK_FILE, `${process.pid} ${Date.now()}`, { flag: 'wx' });
        lockAcquired = true;
        return true;
      } catch (e4) { return false; }
    }
    return false;
  }
}

function releaseLock() {
  if (!lockAcquired) return;
  try {
    const [pid] = fs.readFileSync(LOCK_FILE, 'utf-8').trim().split(/\s+/);
    if (parseInt(pid, 10) === process.pid) fs.unlinkSync(LOCK_FILE);
  } catch (e) {}
  lockAcquired = false;
}

async function closeBrowser() {
  if (browser) {
    try { await browser.close(); } catch (e) {}
    browser = null;
  }
}

async function main() {
  if (!acquireLock()) {
    console.error('已有Playwright任务在运行，跳过');
    process.exitCode = 75;
    return;
  }

  const onSignal = async () => {
    await closeBrowser();
    releaseLock();
    process.exit(130);
  };
  process.on('SIGINT', onSignal);
  process.on('SIGTERM', onSignal);

  try {
    browser = await chromium.launchPersistentContext(PROFILE_DIR, {
      headless: true,
      executablePath: CHROME_PATH,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        `--proxy-server=${PROXY}`,
      ],
    });

    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    const html = await page.evaluate(() => {
      const body = document.querySelector('#js_content') || document.body;
      return body ? body.innerHTML : document.documentElement.outerHTML;
    });
    if (!html || html.length < 1000) {
      throw new Error(`内容过短(${html ? html.length : 0}字节)，可能被反爬`);
    }

    const markdown = `---\ntitle: "${await page.title()}"\nurl: "${url}"\n---\n\n${html}`;
    fs.writeFileSync(output, markdown, 'utf-8');
    console.log(`OK: ${output} (${markdown.length} bytes)`);
    process.exitCode = 0;
  } catch (err) {
    console.error('Error:', err.message);
    process.exitCode = 1;
  } finally {
    await closeBrowser();
    releaseLock();
    process.removeListener('SIGINT', onSignal).removeListener('SIGTERM', onSignal);
  }
}

main();
