#!/usr/bin/env node
/**
 * Fetch the latest WeChat album article using Playwright.
 * Uses the baoyu-skills Chrome profile for authentication.
 *
 * Output (stdout): { title, link } as single-line JSON.
 * Exit codes: 0 = success; 1 = failure; 75 = another instance running.
 *
 * Hardening (2026-08-12, per codex audit P0-2/P0-3):
 * - Reverse-sort failure is FATAL: never silently return the first (oldest) item.
 * - No process.exit() inside try/catch (skips finally); use process.exitCode.
 * - Lock file records PID; stale-lock recovery checks the process is alive.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ALBUM_URL = 'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect';
const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PROXY = process.env.MAOTAI_PROXY || 'http://127.0.0.1:7897';
const LOCK_FILE = '/tmp/maotai-playwright.lock';
const LOCK_STALE_MS = 10 * 60 * 1000; // 10 min

let lockAcquired = false;
let browser = null;

function acquireLock() {
  try {
    fs.writeFileSync(LOCK_FILE, `${process.pid} ${Date.now()}`, { flag: 'wx' });
    lockAcquired = true;
    return true;
  } catch (e) {
    // Check stale lock: pid no longer alive or too old
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
        } catch (e2) {
          return false;
        }
      }
    } catch (e2) {
      // Lock file unreadable -> treat as stale
      try { fs.unlinkSync(LOCK_FILE); } catch (e3) {}
      try {
        fs.writeFileSync(LOCK_FILE, `${process.pid} ${Date.now()}`, { flag: 'wx' });
        lockAcquired = true;
        return true;
      } catch (e4) {
        return false;
      }
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

  // Cleanup on signal so browser + lock never leak
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
    await page.waitForSelector('.album__list-item', { timeout: 15000 }).catch(() => {});

    // Verify we are actually on the album page (CDP about:blank guard)
    const finalUrl = page.url();
    if (!finalUrl.includes('mp.weixin.qq.com')) {
      throw new Error(`页面未就位: URL=${finalUrl} (疑似 CDP about:blank 故障)`);
    }

    await page.waitForTimeout(2000);

    // Capture first item BEFORE sorting (oldest)
    const before = await page.evaluate(() => {
      const item = document.querySelector('.album__list-item');
      return item ? (item.getAttribute('data-link') || '') : '';
    });

    // Click 倒序 (reverse) - try multiple strategies, ALL must fail => fatal error
    let clicked = false;
    let clickError = '';
    for (const sel of ['.album-sort-negative-icon', '.album-sort__word', '.album-sort']) {
      try {
        await page.locator(sel).click({ timeout: 3000 });
        clicked = true;
        break;
      } catch (e) { clickError = e.message; }
    }
    if (!clicked) {
      try {
        await page.locator('text=倒序').click({ timeout: 3000 });
        clicked = true;
      } catch (e) { clickError = e.message; }
    }
    if (!clicked) {
      throw new Error(`倒序按钮点击失败: ${clickError || '全部选择器未命中'}`);
    }

    await page.waitForTimeout(3000);

    // Verify sort actually changed: first item should differ from before
    const after = await page.evaluate(() => {
      const item = document.querySelector('.album__list-item');
      return item ? (item.getAttribute('data-link') || '') : '';
    });
    if (!after || after === before) {
      throw new Error('倒序未生效: 点击后首篇文章未变化，疑似排序失败');
    }

    // Verify top-3 titles are in strict reverse-chronological order
    const top3 = await page.evaluate(() => {
      const items = document.querySelectorAll('.album__list-item');
      const out = [];
      for (let i = 0; i < Math.min(3, items.length); i++) {
        out.push(items[i].getAttribute('data-title') || '');
      }
      return out;
    });
    const dates = top3.map(t => (t.match(/(\d{1,2})月(\d{1,2})日/) || []).slice(1).join('-'));
    if (dates.length >= 2) {
      for (let i = 1; i < dates.length; i++) {
        if (!dates[i]) continue;
        const a = dates[i - 1].split('-').map(Number);
        const b = dates[i].split('-').map(Number);
        if (a[0] * 100 + a[1] <= b[0] * 100 + b[1]) {
          throw new Error(`排序校验失败: 前3篇非严格倒序 (${top3.map(t => t.slice(0, 20)).join(' | ')})`);
        }
      }
    }

    // Extract the first article (newest after reverse sort)
    const article = await page.evaluate(() => {
      const item = document.querySelector('.album__list-item');
      if (!item) return null;
      return {
        title: item.getAttribute('data-title') || '',
        link: item.getAttribute('data-link') || '',
      };
    });

    if (!article || !article.link || !article.title) {
      throw new Error('找不到专辑文章 (标题或链接为空)');
    }

    console.log(JSON.stringify(article));
    process.exitCode = 0;
  } catch (err) {
    console.error('Error:', err.message);
    process.exitCode = 1;
  } finally {
    await closeBrowser();
    releaseLock();
    // Remove signal handlers so we don't double-cleanup
    process.removeListener('SIGINT', onSignal).removeListener('SIGTERM', onSignal);
  }
}

main();
