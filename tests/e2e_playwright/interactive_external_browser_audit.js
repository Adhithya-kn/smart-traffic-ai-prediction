
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = '/Users/ak/.gemini/antigravity/brain/8160a1e6-3892-4be7-b20e-f89f927e1df8/screenshots';
const BASE_URL = 'http://127.0.0.1:8089';

async function runExternalBrowserTrace() {
  console.log('====================================================================');
  console.log('🌐 LAUNCHING EXTERNAL BROWSER TO TRACE LIVE SECTION INTERACTION');
  console.log('====================================================================');

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: false,
    slowMo: 100,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--window-size=1440,960',
      '--auto-open-devtools-for-tabs=false'
    ]
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 2
  });

  const page = await context.newPage();

  const issues = [];
  const consoleMessages = [];

  page.on('console', msg => {
    const entry = { type: msg.type(), text: msg.text() };
    consoleMessages.push(entry);
    if (msg.type() === 'error') {
      console.error(`🚨 BROWSER CONSOLE ERROR: ${msg.text()}`);
      issues.push(`Console Error: ${msg.text()}`);
    } else if (msg.type() === 'warning') {
      console.warn(`⚠️ BROWSER CONSOLE WARN: ${msg.text()}`);
    } else {
      console.log(`ℹ️ [Browser Console] ${msg.text()}`);
    }
  });

  page.on('pageerror', err => {
    console.error(`💥 BROWSER RUNTIME EXCEPTION: ${err.message}`);
    issues.push(`Runtime Exception: ${err.message}`);
  });

  page.on('requestfailed', req => {
    console.error(`❌ HTTP REQUEST FAILED: ${req.method()} ${req.url()} - ${req.failure()?.errorText}`);
    issues.push(`Failed Request: ${req.url()}`);
  });

  try {

    console.log('\n--- Step 1: Navigating to Login Page ---');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_01_login_view.png') });

    console.log('--- Step 2: Logging in as Road User (commuter) ---');
    await page.fill('#usernameInput', 'commuter');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');

    await page.waitForNavigation({ timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(1500);

    console.log(`Current URL after authentication: ${page.url()}`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_02_portal_dashboard.png') });

    console.log('\n--- Step 3: Inspecting Header Navigation Bar & Live Switcher ---');
    const btnStandard = await page.$('#tabConsoleStandard');
    const btnLive = await page.$('#tabConsoleLive');

    if (!btnLive) {
      issues.push('Missing #tabConsoleLive in header');
      console.error('❌ CRITICAL: #tabConsoleLive button does not exist in the DOM!');
    } else {
      const isVisible = await btnLive.isVisible();
      const box = await btnLive.boundingBox();
      console.log(`✓ Live Simulation Tab Button visible: ${isVisible}, boundingBox:`, box);
    }

    console.log('\n--- Step 4: Switching to Live Simulation Section ---');
    await page.click('#tabConsoleLive');
    await page.waitForTimeout(1500);

    const isLiveSectionVisible = await page.isVisible('#viewLiveSimulation');
    console.log(`✓ Live Simulation Section visible: ${isLiveSectionVisible}`);
    if (!isLiveSectionVisible) {
      issues.push('viewLiveSimulation remained hidden after clicking #tabConsoleLive');
      console.error('❌ CRITICAL: #viewLiveSimulation is not visible!');
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_03_live_section_active.png') });

    console.log('\n--- Step 5: Checking Live Corridors & KPI Tickers ---');
    const corridors = await page.$$('.live-corridor-item');
    console.log(`✓ Rendered Corridors count: ${corridors.length}`);
    if (corridors.length === 0) {
      issues.push('No live corridors rendered in list');
      console.error('❌ CRITICAL: No live corridors rendered!');
    }

    const avgSpeed = await page.textContent('#kpiLiveAvgSpeed');
    const corridorCount = await page.textContent('#kpiLiveCorridorCount');
    const weather = await page.textContent('#kpiLiveWeather');
    console.log(`✓ Telemetry Tickers: Avg Speed = ${avgSpeed.trim()}, Corridors = ${corridorCount.trim()}, Weather = ${weather.trim()}`);

    console.log('\n--- Step 6: Testing "Inspect Live API Stream" Drawer ---');
    const btnDrawer = await page.$('#btnToggleApiDrawer');
    if (btnDrawer) {
      await btnDrawer.click();
      await page.waitForTimeout(800);
      const isDrawerOpen = await page.isVisible('#liveApiPayloadDrawer');
      console.log(`✓ Live API Drawer Open: ${isDrawerOpen}`);
      const rawJson = await page.textContent('#liveApiRawJson');
      console.log(`✓ Raw JSON snippet: ${rawJson ? rawJson.slice(0, 120) : 'EMPTY'}...`);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_04_drawer_open.png') });
      await btnDrawer.click();
      await page.waitForTimeout(400);
    }

    console.log('\n--- Step 7: Testing Corridor Selection ---');
    const secondCorridor = await page.$('.live-corridor-item:nth-child(2)');
    if (secondCorridor) {
      await secondCorridor.click();
      await page.waitForTimeout(800);

      const inspectorVisible = await page.isVisible('#liveCorridorInspector');
      console.log(`✓ Corridor Inspector visible: ${inspectorVisible}`);

      const inspectedName = await page.textContent('#inspectorRoadName');
      const inspectedSpeed = await page.textContent('#inspectorSpeed');
      const inspectedSource = await page.textContent('#inspectorSourceTag');
      console.log(`✓ Inspected: ${inspectedName.trim()} @ ${inspectedSpeed.trim()} (${inspectedSource.trim()})`);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_05_corridor_inspected.png') });
    }

    console.log('\n--- Step 8: Evaluating Live Route ---');
    await page.selectOption('#liveOriginSelect', 'RD_BLR_01');
    await page.selectOption('#liveDestSelect', 'RD_BLR_11');
    await page.waitForTimeout(400);

    await page.click('#btnLiveEvaluate');
    await page.waitForSelector('#liveRouteResultBox', { state: 'visible', timeout: 8000 });
    await page.waitForTimeout(800);

    const primSpeed = await page.textContent('#livePrimarySpeed');
    const timeSaved = await page.textContent('#liveTimeSaved');
    const narrative = await page.textContent('#liveNarrativeText');

    console.log(`✓ Evaluated Live Route: Speed = ${primSpeed.trim()}, Time Saved = ${timeSaved.trim()}`);
    console.log(`✓ Narrative: ${narrative.trim()}`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_06_route_evaluated.png') });

    console.log('\n--- Step 9: Testing Zone Filter Pills ---');
    const zonePills = await page.$$('#liveZoneFilterPills .filter-pill');
    console.log(`✓ Found ${zonePills.length} zone filter pills`);
    if (zonePills.length > 1) {
      await zonePills[1].click();
      await page.waitForTimeout(600);
      const filteredCorridors = await page.$$('.live-corridor-item');
      console.log(`✓ Filtered corridors count for Indiranagar: ${filteredCorridors.length}`);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_07_zone_filtered.png') });
    }

    console.log('\n--- Step 10: Testing Refresh Live Feeds Button ---');
    await page.click('#btnRefreshLive');
    await page.waitForTimeout(1500);
    const syncTime = await page.textContent('#liveLastSyncTime');
    console.log(`✓ Sync Time after refresh: ${syncTime.trim()}`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_08_live_refreshed.png') });

    console.log('\n--- Step 11: Testing Round-Trip Navigation (Standard <-> Live) ---');
    await page.click('#tabConsoleStandard');
    await page.waitForTimeout(800);
    console.log('✓ Switched back to Standard: viewCommuter visible =', await page.isVisible('#viewCommuter'));

    await page.click('#tabConsoleLive');
    await page.waitForTimeout(800);
    console.log('✓ Switched back to Live: viewLiveSimulation visible =', await page.isVisible('#viewLiveSimulation'));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ext_09_roundtrip_complete.png') });

    console.log('\n====================================================================');
    console.log('🏁 TRACE COMPLETE');
    console.log(`Total issues identified: ${issues.length}`);
    if (issues.length > 0) {
      console.log('Issues:', JSON.stringify(issues, null, 2));
    } else {
      console.log('🎉 No critical UI breakage detected during automated flow!');
    }
    console.log('====================================================================');

  } catch (err) {
    console.error('Fatal audit failure:', err);
    issues.push(`Fatal Error: ${err.message}`);
  } finally {

    await page.waitForTimeout(2000);
    await browser.close();
  }
}

runExternalBrowserTrace();
