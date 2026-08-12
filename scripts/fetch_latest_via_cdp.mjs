#!/usr/bin/env node

// Uses Chrome DevTools Protocol directly to open the WeChat album page,
// click the 倒序 button via CSS selector, and extract the latest article.
// Unlike agent-browser, this uses Chrome's built-in CDP WebSocket directly.

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const AGENT_BROWSER_BIN = process.env.AGENT_BROWSER_BIN || 
  '/Users/ailubo/.workbuddy/binaries/node/versions/22.22.2/bin/agent-browser';
const SESSION = 'maotai-daily';
const PROXY = process.env.AGENT_BROWSER_PROXY || 'http://127.0.0.1:7897';
const ALBUM_URL = 'https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzk0NzI1MjY4Ng==&action=getalbum&album_id=4328328528879271941&scene=126#wechat_redirect';

import { spawn } from 'child_process';
import { WebSocket } from 'ws';

function browser(...args) {
  return new Promise((resolve, reject) => {
    const proc = spawn(AGENT_BROWSER_BIN, ['--session', SESSION, '--proxy', PROXY, ...args], {
      stdio: ['pipe', 'pipe', 'pipe']
    });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', d => stdout += d);
    proc.stderr.on('data', d => stderr += d);
    proc.on('close', code => {
      if (code === 0) resolve(stdout.trim());
      else reject(new Error(stderr.trim() || `Exit ${code}: ${stdout.trim()}`));
    });
    proc.on('error', reject);
  });
}

async function main() {
  try {
    // Step 1: Open the page
    console.log('Opening album page...');
    await browser('open', ALBUM_URL);
    
    // Step 2: Wait for load
    console.log('Waiting for page load...');
    await browser('wait', '--load', 'networkidle').catch(() => browser('wait', '3000'));
    
    // Step 3: Click 倒序 using CSS selector instead of XPath
    console.log('Clicking 倒序 button...');
    const clickResult = await browser('eval', `
      (() => {
        // Try CSS selector first (more robust than XPath)
        let node = document.querySelector('.album-sort-negative-icon');
        if (!node) node = document.querySelector('.album-sort__word');
        if (!node) {
          // Fallback: find by text content
          const spans = document.querySelectorAll('span');
          for (const span of spans) {
            if (span.textContent.trim() === '倒序') {
              node = span;
              break;
            }
          }
        }
        if (!node) {
          // Try XPath
          const xpathNode = document.evaluate(
            "//span[normalize-space(text())='倒序']",
            document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
          ).singleNodeValue;
          if (xpathNode) node = xpathNode;
        }
        if (!node) throw new Error('找不到倒序按钮');
        // Click the parent clickable element
        const clickable = node.closest('div, button, a, span');
        (clickable || node).click();
        return 'clicked ' + (node.className || node.tagName);
      })()
    `);
    console.log('Click result:', clickResult);
    
    // Step 4: Wait for re-render
    console.log('Waiting for re-render...');
    await browser('wait', '3000');
    
    // Step 5: Extract the first article
    console.log('Extracting first article...');
    const result = await browser('eval', `
      (() => {
        const item = document.querySelector(".album__list-item");
        if (!item) throw new Error("找不到专辑文章");
        const title = item.getAttribute("data-title") || item.dataset.title || "";
        const link = item.getAttribute("data-link") || item.dataset.link || "";
        if (!link) throw new Error("第一篇文章缺少 data-link");
        return { title, link };
      })()
    `);
    console.log(JSON.stringify(JSON.parse(result)));
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  } finally {
    // Cleanup
    await browser('close').catch(() => {});
  }
}

main();
