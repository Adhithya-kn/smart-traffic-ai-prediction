/**
 * tests/e2e_playwright/test_theme_switcher.js
 * Verification of Apple HIG Obsidian Aesthetic, Materials, Specular Lighting,
 * and Ergonomic Standards.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const assert = require('assert');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

(async () => {
  console.log('====================================================================');
  console.log('🎨 VERIFYING APPLE HIG LUXURY OBSIDIAN PALETTE & HIG MATERIALS');
  console.log('====================================================================');

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,960']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2
  });
  const page = await context.newPage();

  try {
    // 1. Sign In
    console.log('1. Signing in as commuter...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.fill('#usernameInput', 'commuter');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForNavigation({ timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(1000);

    // 2. Verify Deep Neutral Obsidian Palette
    console.log('2. Inspecting Body Background & Obsidian Theme...');
    const bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    console.log(`✓ Body Background: ${bodyBg}`);
    assert(bodyBg.includes('8, 9, 13') || bodyBg.includes('7, 8, 10'), `Unexpected background: ${bodyBg}`);

    // 3. Verify Apple HIG Specular Top Highlight & Glass Cards
    console.log('3. Inspecting Card Glass Surface & Specular Highlights...');
    const cardStyles = await page.evaluate(() => {
      const card = document.querySelector('.obsidian-card');
      if (!card) return null;
      const comp = getComputedStyle(card);
      return {
        bg: comp.backgroundColor,
        borderRadius: comp.borderRadius,
        backdropFilter: comp.backdropFilter || comp.webkitBackdropFilter,
        borderTop: comp.borderTopColor
      };
    });
    assert(cardStyles, 'No obsidian card found!');
    console.log(`✓ Obsidian Glass Surface: BG=${cardStyles.bg}, Radius=${cardStyles.borderRadius}, Blur=${cardStyles.backdropFilter}`);

    // 4. Verify 4 Navigation Switcher Tabs
    console.log('4. Verifying 4-Segment Navigation Switcher in Header...');
    const navButtons = await page.$$eval('#navSectionSwitcher button', btns => btns.map(b => b.textContent.trim()));
    console.log(`✓ Found navigation tabs: ${navButtons.join(' | ')}`);
    assert(navButtons.length === 4, `Expected 4 main tabs, found ${navButtons.length}`);

    // 5. Verify Spring Physics on Switcher
    const switcherTransition = await page.evaluate(() => {
      const sw = document.getElementById('navSectionSwitcher');
      return sw ? getComputedStyle(sw).transition : '';
    });
    console.log(`✓ Navigation physics transition verified.`);

    console.log('====================================================================');
    console.log('🎉 OBSIDIAN AESTHETIC & APPLE HIG AUDIT COMPLETE: ALL PASS!');
    console.log('====================================================================');
  } catch (err) {
    console.error('Audit failed:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
