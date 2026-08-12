#!/usr/bin/env node
/**
 * Fetch the latest N articles from the WeChat album (reverse order, scroll-loading).
 * Output (stdout): JSON array [{ title, link, date }] where date is parsed from title.
 *
 * Exit codes: 0 = success; 1 = failure; 75 = another instance running.
 * Hardening (2026-08-12): no process.exit in try/catch; PID-aware lock; strict cleanup.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ALBUM_URL = 'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect';
const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PROXY = process.env.MAOTAI_PROXY || 'http://127.0.0.1:7897';
const LOCK_FILE = '/tmp/maotai-playwright.lock';
const LOCK_STALE_MS = 10 * 60 * 1000;
const N = parseInt(process.argv[2] || '8', 10);
const MAX_SCROLL_ROUNDS = 40;

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

function parseDateFromTitle(title) {
  const m = title.match(/(\d{1,2})月(\d{1,2})日/);
  if (!m) return '';
  const month = parseInt(m[1], 10).toString().padStart(2, '0');
  const day = parseInt(m[2], 10).toString().padStart(2, '0');
  return `2026-${month}-${day}`;
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
    await page.goto(ALBUM_URL, { waitUntil: 'networkidle', timeout: 60000 });

    // CDP about:blank guard
    if (!page.url().includes('mp.weixin.qq.com')) {
      throw new Error(`页面未就位: URL=${page.url()}`);
    }

    await page.waitForSelector('.album__list-item', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);

    // Click 倒序 - failure is fatal
    let clicked = false;
    for (const sel of ['.album-sort-negative-icon', '.album-sort__word', '.album-sort']) {
      try { await page.locator(sel).click({ timeout: 3000 }); clicked = true; break; } catch (e) {}
    }
    if (!clicked) {
      try { await page.locator('text=倒序').click({ timeout: 3000 }); clicked = true; } catch (e) {}
    }
    if (!clicked) {
      throw new Error('倒序按钮点击失败');
    }
    await page.waitForTimeout(3000);

    // Scroll-load until we have N items or reach the end
    let lastCount = 0;
    for (let round = 0; round < MAX_SCROLL_ROUNDS; round++) {
      const count = await page.evaluate(() => document.querySelectorAll('.album__list-item').length);
      if (count >= N) break;
      if (count === lastCount) {
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(1500);
        const count2 = await page.evaluate(() => document.querySelectorAll('.album__list-item').length);
        if (count2 === count) break;
        lastCount = count2;
        continue;
      }
      lastCount = count;
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(1500);
    }

    // Extract first N articles (reverse order => newest first)
    const articles = await page.evaluate((n) => {
      const items = document.querySelectorAll('.album__list-item');
      const result = [];
      for (let i = 0; i < Math.min(n, items.length); i++) {
        result.push({
          title: items[i].getAttribute('data-title') || '',
          link: items[i].getAttribute('data-link') || '',
        });
      }
      return result;
    }, N);

    if (articles.length === 0) {
      throw new Error('找不到专辑文章');
    }

    const withDates = articles.map(a => ({ ...a, date: parseDateFromTitle(a.title) }));
    console.log(JSON.stringify(withDates, null, 2));
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
