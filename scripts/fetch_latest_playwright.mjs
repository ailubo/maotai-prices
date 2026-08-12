#!/usr/bin/env node
/**
 * Fetch the latest WeChat album article using Playwright.
 * Uses the baoyu-skills Chrome profile for authentication.
 * Returns: { title, link } as JSON on stdout.
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';

const ALBUM_URL = 'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect';
const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');

async function main() {
  // Try to acquire a file lock
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
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        `--proxy-server=http://127.0.0.1:7897`,
      ],
    });
    
    const page = await browser.newPage();
    
    // Navigate to album page
    await page.goto(ALBUM_URL, { waitUntil: 'networkidle', timeout: 60000 });
    
    // Wait for the article list to load
    await page.waitForSelector('.album__list-item', { timeout: 30000 }).catch(() => {});
    
    // Try to click 倒序 button - use multiple selector strategies
    let clicked = false;
    
    // Strategy 1: CSS class
    for (const sel of ['.album-sort-negative-icon', '.album-sort__word', 'span:has-text("倒序")']) {
      try {
        const btn = await page.$(sel);
        if (btn) {
          await btn.click();
          clicked = true;
          break;
        }
      } catch(e) {}
    }
    
    // Strategy 2: Click parent of 倒序 text
    if (!clicked) {
      try {
        const parent = await page.locator('text=倒序').locator('..');
        await parent.click();
        clicked = true;
      } catch(e) {}
    }
    
    if (!clicked) {
      console.error('点击倒序失败');
      // Continue anyway - maybe default is already reverse order
    }
    
    // Wait for re-render
    await page.waitForTimeout(3000);
    
    // Extract first article
    const article = await page.evaluate(() => {
      const item = document.querySelector('.album__list-item');
      if (!item) return null;
      const title = item.getAttribute('data-title') || item.dataset.title || '';
      const link = item.getAttribute('data-link') || item.dataset.link || '';
      return { title, link };
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
