#!/usr/bin/env node
/**
 * Fetch the latest N articles from the WeChat album (reverse order).
 * Returns JSON array: [{ title, link, date }]
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ALBUM_URL = 'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect';
const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const N = parseInt(process.argv[2] || '8', 10);

async function main() {
  const lockFile = '/tmp/maotai-playwright.lock';
  try {
    fs.writeFileSync(lockFile, String(process.pid), { flag: 'wx' });
  } catch (e) {
    console.error('已有Playwright任务在运行，跳过');
    process.exit(75);
  }
  const cleanup = () => { try { fs.unlinkSync(lockFile); } catch(e) {} };

  let browser;
  try {
    browser = await chromium.launchPersistentContext(PROFILE_DIR, {
      headless: true,
      executablePath: CHROME_PATH,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--proxy-server=http://127.0.0.1:7897',
      ],
    });

    const page = await browser.newPage();
    await page.goto(ALBUM_URL, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForSelector('.album__list-item', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);

    // Click 倒序
    let clicked = false;
    try { await page.locator('.album-sort-negative-icon').click({ timeout: 5000 }); clicked = true; } catch(e) {}
    if (!clicked) { try { await page.locator('text=倒序').click({ timeout: 5000 }); clicked = true; } catch(e) {} }
    if (!clicked) { try { await page.locator('.album-sort__word').click({ timeout: 5000 }); clicked = true; } catch(e) {} }
    if (!clicked) { try { await page.locator('.album-sort').click({ timeout: 5000 }); clicked = true; } catch(e) {} }

    await page.waitForTimeout(3000);

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
      console.error('找不到专辑文章');
      process.exit(1);
    }

    console.log(JSON.stringify(articles, null, 2));
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  } finally {
    if (browser) await browser.close().catch(() => {});
    cleanup();
  }
}

main();
