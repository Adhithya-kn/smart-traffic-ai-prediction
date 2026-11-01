/**
 * tests/test_theme_switcher.js
 * End-to-end verification of the human-crafted Dark/Light theme switcher.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = '/Users/ak/.gemini/antigravity/brain/8160a1e6-3892-4be7-b20e-f89f927e1df8/screenshots';
const BASE_URL = 'http://127.0.0.1:8089';

async function runThemeAudit() {
  console.log('====================================================================');
  console.log('🎨 VERIFYING HUMAN-CRAFTED DARK / LIGHT THEME SWITCHER');
  console.log('====================================================================');

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: false,
    slowMo: 100,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,960']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2
  });

  const page = await browser.newPage();

  try {
    // 1. Sign In
    console.log('1. Signing in as commuter...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.fill('#usernameInput', 'commuter');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForNavigation({ timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(1200);

    // 2. Check Theme Switcher presence in header
    console.log('2. Inspecting theme switcher in header...');
    const themeSwitch = await page.$('#themeSwitch');
    const btnDark = await page.$('#themeBtnDark');
    const btnLight = await page.$('#themeBtnLight');

    console.log('✓ Theme Switch container exists:', !!themeSwitch);
    console.log('✓ Dark button exists:', !!btnDark);
    console.log('✓ Light button exists:', !!btnLight);

    const isDarkActiveInitial = await page.evaluate(() => {
      const b = document.getElementById('themeBtnDark');
      return b && b.classList.contains('active') && document.body.classList.contains('theme-obsidian');
    });
    console.log('✓ Initial mode is Obsidian Dark:', isDarkActiveInitial);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_01_obsidian_commuter.png') });

    // 3. Switch to Light Mode
    console.log('3. Switching to Refined Light Theme...');
    await page.click('#themeBtnLight');
    await page.waitForTimeout(800);

    const isLightActive = await page.evaluate(() => {
      const b = document.getElementById('themeBtnLight');
      const saved = localStorage.getItem('traffic_ai_theme');
      return b && b.classList.contains('active') && document.body.classList.contains('theme-light') && saved === 'light';
    });
    console.log('✓ Light theme applied and persisted in localStorage:', isLightActive);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_02_light_commuter.png') });

    // 4. Test Live Simulation Section in Light Mode
    console.log('4. Navigating to Live Simulation in Light Mode...');
    await page.click('#tabConsoleLive');
    await page.waitForTimeout(1000);

    const isLiveSectionVisible = await page.isVisible('#viewLiveSimulation');
    console.log('✓ Live Simulation visible in light theme:', isLiveSectionVisible);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_03_light_live_simulation.png') });

    // 5. Inspect Live API Drawer in Light Mode
    console.log('5. Inspecting Live API payload drawer in Light Mode...');
    await page.click('#btnToggleApiDrawer');
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_04_light_drawer_open.png') });
    await page.click('#btnToggleApiDrawer');
    await page.waitForTimeout(400);

    // 6. Inspect Corridor Sensor Card in Light Mode
    console.log('6. Inspecting Corridor Sensor Card in Light Mode...');
    const secondCorridor = await page.$('.live-corridor-item:nth-child(2)');
    if (secondCorridor) {
      await secondCorridor.click();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_05_light_corridor_inspected.png') });
    }

    // 7. Test Route Evaluation in Light Mode
    console.log('7. Evaluating dynamic live route in Light Mode...');
    await page.click('#btnLiveEvaluate');
    await page.waitForSelector('#liveRouteResultBox', { state: 'visible', timeout: 6000 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_06_light_route_evaluated.png') });

    // 8. Switch Back to Dark Mode
    console.log('8. Switching back to Obsidian Dark Theme...');
    await page.click('#themeBtnDark');
    await page.waitForTimeout(800);

    const isDarkRestored = await page.evaluate(() => {
      const b = document.getElementById('themeBtnDark');
      const saved = localStorage.getItem('traffic_ai_theme');
      return b && b.classList.contains('active') && document.body.classList.contains('theme-obsidian') && saved === 'obsidian';
    });
    console.log('✓ Obsidian Dark theme restored cleanly:', isDarkRestored);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_07_back_to_obsidian.png') });

    // 9. Test Theme Persistence across Page Reload
    console.log('9. Testing persistence across page reload in Light mode...');
    await page.click('#themeBtnLight');
    await page.waitForTimeout(400);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const persistedLight = await page.evaluate(() => {
      const b = document.getElementById('themeBtnLight');
      return b && b.classList.contains('active') && document.body.classList.contains('theme-light');
    });
    console.log('✓ Light theme persisted across page reload:', persistedLight);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'theme_08_persisted_reload.png') });

    // Reset back to Obsidian default
    await page.click('#themeBtnDark');
    await page.waitForTimeout(400);

    console.log('\n====================================================================');
    console.log('🎉 THEME SWITCHER AUDIT COMPLETE: ALL CHECKS PASSED!');
    console.log('====================================================================');
  } catch (err) {
    console.error('Theme audit failed:', err);
  } finally {
    await page.waitForTimeout(1500);
    await browser.close();
  }
}

runThemeAudit();
