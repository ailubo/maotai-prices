#!/usr/bin/env node
/**
 * Fetch a WeChat article directly with Playwright and save HTML content.
 * Usage: node fetch_article_playwright.cjs <url> <output.md>
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const url = process.argv[2];
const output = process.argv[3];
const PROFILE_DIR = path.join(process.env.HOME, 'Library', 'Application Support', 'baoyu-skills', 'chrome-profile');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function main() {
  const lockFile = '/tmp/maotai-playwright.lock';
  try {
    fs.writeFileSync(lockFile, String(process.pid), { flag: 'wx' });
  } catch (e) {
    console.error('已有Playwright任务在运行');
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
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    // Extract article body HTML
    const html = await page.evaluate(() => {
      const body = document.querySelector('#js_content') || document.body;
      return body ? body.innerHTML : document.documentElement.outerHTML;
    });
    if (!html || html.length < 1000) {
      console.error(`内容过短(${html ? html.length : 0}字节)，可能被反爬`);
      process.exit(1);
    }
    const markdown = `---\ntitle: "${await page.title()}"\nurl: "${url}"\n---\n\n${html}`;
    fs.writeFileSync(output, markdown, 'utf-8');
    console.log(`OK: ${output} (${markdown.length} bytes)`);
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  } finally {
    if (browser) await browser.close().catch(() => {});
    cleanup();
  }
}

main();
