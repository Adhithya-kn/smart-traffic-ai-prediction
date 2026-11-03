const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = '/Users/ak/.gemini/antigravity/brain/8160a1e6-3892-4be7-b20e-f89f927e1df8/screenshots';

(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,960']
  });

  const page = await browser.newPage();

  const consoleLogs = [];
  const pageErrors = [];
  page.on('console', msg => consoleLogs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => pageErrors.push(err.toString()));

  console.log('1. Navigating to /login...');
  await page.goto('http://127.0.0.1:8089/login', { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'debug_01_login_page.png') });

  console.log('2. Entering credentials (commuter / Admin@123)...');
  await page.fill('#usernameInput', 'commuter');
  await page.fill('#passwordInput', 'Admin@123');
  await page.click('#submitBtn');

  console.log('3. Waiting for portal navigation...');
  await page.waitForNavigation({ timeout: 6000 }).catch(e => console.log('Navigation event notice:', e.message));
  await page.waitForTimeout(1500);
  console.log('Current URL after login:', page.url());
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'debug_02_after_login.png') });

  console.log('4. Checking switcher buttons...');
  const btnStandard = await page.$('#tabConsoleStandard');
  const btnLive = await page.$('#tabConsoleLive');
  console.log('tabConsoleStandard visible:', await btnStandard?.isVisible());
  console.log('tabConsoleLive visible:', await btnLive?.isVisible());

  console.log('5. Clicking Live Simulation tab (#tabConsoleLive)...');
  await page.click('#tabConsoleLive');
  await page.waitForTimeout(1500);
  console.log('Current URL after clicking Live tab:', page.url());
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'debug_03_live_section_opened.png') });

  const viewLive = await page.$('#viewLiveSimulation');
  const viewCommuter = await page.$('#viewCommuter');
  const viewAuthority = await page.$('#viewAuthority');
  console.log('viewLive display / isVisible:', await viewLive?.isVisible());
  console.log('viewCommuter display / isVisible:', await viewCommuter?.isVisible());
  console.log('viewAuthority display / isVisible:', await viewAuthority?.isVisible());

  const corridorListContainer = await page.$('#liveCorridorListContainer');
  const corridorItems = await page.$$('.live-corridor-item');
  console.log('Corridor list container visible:', await corridorListContainer?.isVisible());
  console.log('Number of live corridor items rendered:', corridorItems.length);

  const streamBar = await page.$('#liveApiStreamBar');
  console.log('Live API Stream Bar visible:', await streamBar?.isVisible());

  console.log('6. Clicking #btnToggleApiDrawer...');
  const btnToggleDrawer = await page.$('#btnToggleApiDrawer');
  if (btnToggleDrawer) {
    await btnToggleDrawer.click();
    await page.waitForTimeout(600);
    const drawerVisible = await page.isVisible('#liveApiPayloadDrawer');
    console.log('Drawer visible:', drawerVisible);
    const rawJson = await page.textContent('#liveApiRawJson');
    console.log('Raw JSON preview:', rawJson ? rawJson.slice(0, 100) : 'EMPTY');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'debug_04_drawer_open.png') });
  }

  console.log('7. Clicking a corridor card...');
  if (corridorItems.length > 0) {
    await corridorItems[0].click();
    await page.waitForTimeout(600);
    const inspectorVisible = await page.isVisible('#liveCorridorInspector');
    console.log('Inspector visible after click:', inspectorVisible);
    const roadName = await page.textContent('#inspectorRoadName');
    console.log('Selected road name:', roadName);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'debug_05_corridor_selected.png') });
  } else {
    console.log('WARNING: No corridor items found in #liveCorridorListContainer!');
    const containerHtml = await corridorListContainer?.innerHTML();
    console.log('Container HTML:', containerHtml);
  }

  console.log('8. Testing Evaluate Live Route button...');
  const btnEval = await page.$('#btnLiveEvaluate');
  console.log('btnLiveEvaluate visible:', await btnEval?.isVisible());
  if (btnEval) {
    await btnEval.click();
    await page.waitForTimeout(1500);
    const resultBox = await page.isVisible('#liveRouteResultBox');
    console.log('liveRouteResultBox visible:', resultBox);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'debug_06_route_eval.png') });
  }

  console.log('\n--- PAGE ERRORS ---');
  console.log(JSON.stringify(pageErrors, null, 2));

  console.log('\n--- CONSOLE LOGS ---');
  console.log(JSON.stringify(consoleLogs.filter(l => l.type === 'error' || l.type === 'warning'), null, 2));

  await browser.close();
})();
