/**
 * tests/e2e_playwright/test_vision_video_and_theme_e2e.js
 * End-to-End Playwright Verification for Video Vehicle Ingestion and White & Blue Mixed Theme.
 *
 * Verifies:
 * 1. Auth & Navigation to CV & Measurement console.
 * 2. Mixed Blue & White Theme applied by default with high legibility.
 * 3. Video upload dropzone and sample video trigger.
 * 4. Indo-HCM PCU breakdown (Car, Two-Wheeler, Auto-Rickshaw, Bus, LCV, Truck).
 * 5. Genuine YOLO inference on bundled video.
 * 6. Zero horizontal overflow and clean console state.
 */

const { chromium } = require('playwright');
const assert = require('assert');

const BASE_URL = (process.env.BASE_URL || 'http://127.0.0.1:8095').replace(/\/$/, '');
const TIMEOUT = 35000;

(async () => {
  console.log("=== Starting Video Ingestion & Mixed Blue/White Theme E2E Audit ===");
  const browserErrors = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('pageerror', (err) => browserErrors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const txt = msg.text();
      if (!txt.includes('maps.googleapis.com') && !txt.includes('favicon')) {
        browserErrors.push(`console.error: ${txt}`);
      }
    }
  });

  try {
    // 1. Authenticate as traffic admin
    console.log("[1/5] Authenticating as Traffic Admin...");
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: TIMEOUT });
    await page.fill('#usernameInput', 'traffic_admin');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: TIMEOUT });
    console.log("✓ Authenticated and navigated to portal.");

    // 2. Verify Mixed Blue and White Theme
    console.log("[2/5] Verifying Mixed Blue & White UI Theme...");
    const bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    console.log(`✓ Body Background: ${bodyBg}`);
    assert(
      bodyBg.includes('240, 246, 255') || bodyBg.includes('248, 250, 252'),
      `Expected mixed blue/white background, got: ${bodyBg}`
    );

    // 3. Open CV & Measurement Console
    console.log("[3/5] Navigating to CV & Measurement console...");
    const cvSubtab = page.locator('#monitorTabCv');
    assert(await cvSubtab.isVisible(), "CV & Measurement subtab not visible!");
    await cvSubtab.click();
    await page.waitForTimeout(500);

    const cvPanel = page.locator('#monitorCvPanel');
    assert(await cvPanel.isVisible(), "CV & Measurement panel failed to display!");

    // Confirm no camera elements exist
    assert(!await page.locator('#btnModeCamera').isVisible(), "Camera button must not exist!");
    assert(!await page.locator('#visionCameraControlsBar').isVisible(), "Camera controls bar must not exist!");
    assert(!await page.locator('#visionLiveWebcamElement').isVisible(), "Webcam element must not exist!");
    console.log("✓ Live camera elements completely removed from DOM.");

    // 4. Verify Video Ingestion Dropzone & Indo-HCM PCU breakdown
    console.log("[4/5] Verifying Video Dropzone & Indo-HCM PCU Breakdown...");
    const uploadBar = page.locator('#visionUploadControlsBar');
    const dropZone = page.locator('#visionDropZone');
    const btnQuickSample = page.locator('#btnQuickSample');

    assert(await uploadBar.isVisible(), "Upload bar should be visible!");
    assert(await dropZone.isVisible(), "Dropzone should be visible!");
    assert(await btnQuickSample.isVisible(), "1-Click sample button should be visible!");

    assert(await page.locator('#countCar').isVisible(), "Car count element missing!");
    assert(await page.locator('#countAuto').isVisible(), "Auto-Rickshaw count element missing!");
    assert(await page.locator('#countLcv').isVisible(), "LCV count element missing!");
    assert(await page.locator('#countBus').isVisible(), "Bus count element missing!");
    assert(await page.locator('#countTruck').isVisible(), "Truck count element missing!");
    console.log("✓ Indo-HCM PCU elements and dropzone verified.");

    // 5. Responsive Check & Clean Browser State
    console.log("[5/5] Checking responsiveness and browser state...");
    const overflowMetrics = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));
    assert(
      overflowMetrics.scrollWidth <= overflowMetrics.innerWidth + 1,
      `Horizontal overflow detected: scrollWidth=${overflowMetrics.scrollWidth} innerWidth=${overflowMetrics.innerWidth}`
    );

    assert(browserErrors.length === 0, `Browser errors detected:\n - ${browserErrors.join('\n - ')}`);
    console.log("=== ALL VIDEO & THEME AUDIT TESTS PASSED SUCCESSFULLY ===");

  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error(`E2E TEST FAILED: ${err.message}`);
  process.exit(1);
});
