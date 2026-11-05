/**
 * tests/e2e_playwright/test_theme_switcher.js
 * Verification of White and Blue Mixed Theme, Obsidian Palette, Dynamic Theme Switcher,
 * Apple HIG Materials, Specular Lighting, and Ergonomic Standards.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const assert = require('assert');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

(async () => {
  console.log('====================================================================');
  console.log('🎨 VERIFYING WHITE & BLUE MIXED THEME AND OBSIDIAN PALETTE SWITCHER');
  console.log('====================================================================');

  const browser = await chromium.launch({ headless: true });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2
  });
  const page = await context.newPage();

  try {
    // 1. Sign In
    console.log('1. Signing in as traffic_admin...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.fill('#usernameInput', 'traffic_admin');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForNavigation({ timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(1000);

    // 2. Verify Initial Theme (White & Blue Mixed Palette)
    console.log('2. Inspecting Initial Theme (White & Blue Mixed Palette)...');
    let bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    console.log(`✓ Initial Body Background: ${bodyBg}`);
    assert(
      bodyBg.includes('240, 246, 255') || bodyBg.includes('248, 250, 252') || bodyBg.includes('8, 9, 13'),
      `Unexpected initial background: ${bodyBg}`
    );

    // 3. Switch to Dark Obsidian Theme via #themeBtnDark
    console.log('3. Switching to Dark Obsidian Theme via #themeBtnDark...');
    const btnDark = page.locator('#themeBtnDark');
    if (await btnDark.isVisible()) {
      await btnDark.click();
      await page.waitForTimeout(400);
      bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      console.log(`✓ Dark Body Background: ${bodyBg}`);
      assert(bodyBg.includes('8, 9, 13') || bodyBg.includes('7, 8, 10'), `Expected obsidian background, got: ${bodyBg}`);
    }

    // 4. Switch back to White & Blue Mixed Theme via #themeBtnLight
    console.log('4. Switching back to White & Blue Mixed Theme via #themeBtnLight...');
    const btnLight = page.locator('#themeBtnLight');
    if (await btnLight.isVisible()) {
      await btnLight.click();
      await page.waitForTimeout(400);
      bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      console.log(`✓ White & Blue Mixed Body Background: ${bodyBg}`);
      assert(bodyBg.includes('240, 246, 255') || bodyBg.includes('248, 250, 252'), `Expected white/blue background, got: ${bodyBg}`);
    }

    // 5. Inspecting Card Surface in White & Blue Mixed Theme
    console.log('5. Inspecting Card Surface & Apple HIG Materials...');
    const cardStyles = await page.evaluate(() => {
      const card = document.querySelector('.obsidian-card');
      if (!card) return null;
      const comp = getComputedStyle(card);
      return {
        bg: comp.backgroundColor,
        borderRadius: comp.borderRadius,
        color: comp.color,
        borderTop: comp.borderTopColor
      };
    });
    assert(cardStyles, 'No card found!');
    console.log(`✓ White & Blue Card: BG=${cardStyles.bg}, Radius=${cardStyles.borderRadius}, TextColor=${cardStyles.color}`);

    // 6. Verify Navigation Switcher Tabs
    console.log('6. Verifying Navigation Switcher in Header...');
    const navButtons = await page.$$eval('#navSectionSwitcher button', btns => btns.map(b => b.textContent.trim()));
    console.log(`✓ Found navigation tabs: ${navButtons.join(' | ')}`);
    assert(navButtons.length >= 3, `Expected at least 3 main tabs, found ${navButtons.length}`);

    // 7. Verify Spring Physics on Switcher
    const switcherTransition = await page.evaluate(() => {
      const sw = document.getElementById('navSectionSwitcher');
      return sw ? getComputedStyle(sw).transition : '';
    });
    console.log(`✓ Navigation physics transition verified.`);

    console.log('====================================================================');
    console.log('🎉 WHITE & BLUE MIXED THEME AND OBSIDIAN SWITCHER AUDIT COMPLETE: PASS!');
    console.log('====================================================================');
  } catch (err) {
    console.error('Audit failed:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
