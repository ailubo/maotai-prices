#!/usr/bin/env node
/**
 * Fetch the latest WeChat album article using Playwright.
 * Uses the baoyu-skills Chrome profile for authentication.
 * Returns: { title, link } as JSON on stdout.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ALBUM_URL = 'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect';
const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');
// Use the system Chrome instead of Playwright's bundled Chromium
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

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
    
    // Wait for album content to load
    await page.waitForSelector('.album__list-item', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    
    // Click 倒序: try multiple strategies
    let clicked = false;
    try {
      await page.locator('.album-sort-negative-icon').click({ timeout: 5000 });
      clicked = true;
    } catch(e) {}
    
    if (!clicked) {
      try {
        await page.locator('text=倒序').click({ timeout: 5000 });
        clicked = true;
      } catch(e) {}
    }
    
    if (!clicked) {
      try {
        // Click the parent div of the sort icon
        await page.locator('.album-sort__word').click({ timeout: 5000 });
        clicked = true;
      } catch(e) {}
    }
    
    await page.waitForTimeout(3000);
    
    // Get first article
    const article = await page.evaluate(() => {
      const item = document.querySelector('.album__list-item');
      if (!item) return null;
      return {
        title: item.getAttribute('data-title') || '',
        link: item.getAttribute('data-link') || '',
      };
    });
    
    if (!article || !article.link) {
      console.error('找不到专辑文章');
      process.exit(1);
    }
    
    console.log(JSON.stringify(article));
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  } finally {
    if (browser) await browser.close().catch(() => {});
    cleanup();
  }
}

main();
