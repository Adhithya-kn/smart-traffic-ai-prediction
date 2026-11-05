#!/usr/bin/env node
/**
 * tests/e2e_playwright/phase4_smoke_8090.js - Phase 4 deployment/UI smoke check
 *
 * Runs against an already-running application server (default: http://127.0.0.1:8090).
 * It verifies the static UI ship, auth redirect, static architecture assets, the health
 * endpoint and basic responsive behavior. It is NOT part of pytest and CI only runs it
 * from the explicit e2e workflow that starts its own server.
 *
 * Usage:
 *   npm run e2e:smoke                       # if wired in package.json
 *   BASE_URL=http://127.0.0.1:8090 node tests/e2e_playwright/phase4_smoke_8090.js
 */

const { chromium } = require('playwright');

const BASE_URL = (process.env.BASE_URL || 'http://127.0.0.1:8090').replace(/\/$/, '');
const TIMEOUT = Number(process.env.E2E_TIMEOUT_MS || 30000);
const WIDTHS = [1280, 1440, 1920];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

(async () => {
  const browserErrors = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on('pageerror', (err) => browserErrors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') browserErrors.push(`console.error: ${msg.text()}`);
  });

  try {
    // 1. Health endpoint (Render healthCheckPath + Docker HEALTHCHECK target).
    const health = await context.request.get(`${BASE_URL}/api/health`, { timeout: TIMEOUT });
    assert(health.ok(), `GET /api/health returned ${health.status()}`);

    // 2. Login page ships and renders.
    const login = await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });
    assert(login && login.ok(), `GET /login returned ${login && login.status()}`);
    assert((await page.title()).trim().length > 0, 'login page has an empty <title>');

    // 3. Unauthenticated /portal must redirect to /login (no fake demo session).
    await page.goto(`${BASE_URL}/portal`, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });
    await page.waitForURL(url => url.pathname.includes('/login'), { timeout: TIMEOUT });
    assert(page.url().includes('/login'), `unauthenticated /portal did not redirect to /login (${page.url()})`);

    // 4. Static assets used by the UI resolve.
    for (const asset of ['/login.html', '/index.html', '/styles.css', '/app.js']) {
      const resp = await context.request.get(`${BASE_URL}${asset}`, { timeout: TIMEOUT });
      assert(resp.ok(), `static asset ${asset} returned ${resp.status()}`);
    }

    // 5. Architecture assets linked from the console footer are served (Docker/Render include them).
    for (const asset of [
      '/architecture/visual_architecture.html',
      '/architecture/beginner_guide.html',
      '/architecture/system_architecture_flowchart.svg',
    ]) {
      const resp = await context.request.get(`${BASE_URL}${asset}`, { timeout: TIMEOUT });
      assert(resp.ok(), `architecture asset ${asset} returned ${resp.status()}`);
    }

    // 6. Responsive login page: no horizontal overflow at required widths.
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });
      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      }));
      assert(
        metrics.scrollWidth <= metrics.innerWidth + 1,
        `horizontal overflow at ${width}px: scrollWidth=${metrics.scrollWidth} innerWidth=${metrics.innerWidth}`
      );
    }

    // 7. No uncaught page errors / console errors during the smoke run.
    assert(browserErrors.length === 0, `browser errors detected:\n - ${browserErrors.join('\n - ')}`);

    console.log(
      'E2E smoke PASS ' +
        JSON.stringify({ baseUrl: BASE_URL, widths: WIDTHS, health: health.status(), checkedArchitectureAssets: 3 })
    );
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error(`E2E smoke FAIL: ${err.message}`);
  process.exit(1);
});
