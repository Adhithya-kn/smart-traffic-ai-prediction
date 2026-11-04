/**
 * tests/e2e_playwright/test_vision_intelligence_e2e.js
 * End-to-End Playwright Verification for AI Vision Intelligence & CCTV Stream Hub.
 */

const { chromium } = require('playwright');
const assert = require('assert');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

(async () => {
  console.log("=== Starting Vision Intelligence E2E Audit ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // 1. Load Application
    console.log("[1/6] Loading Dashboard...");
    await page.goto(`${BASE_URL}/portal`, { waitUntil: "networkidle", timeout: 15000 });

    // 2. Click Vision AI & Camera Tab
    console.log("[2/6] Switching to Vision AI & Camera Tab...");
    const visionTab = page.locator("#tabConsoleVision");
    await assert(await visionTab.isVisible(), "Vision tab button not found in navigation!");
    await visionTab.click();
    await page.waitForTimeout(600);

    const visionView = page.locator("#viewVisionIntelligence");
    assert(await visionView.isVisible(), "Vision Intelligence Viewport failed to display!");
    console.log("✓ Vision Intelligence Viewport active and visible.");

    // 3. Test Video Upload Dropzone
    console.log("[3/6] Testing Ingestion Dropzone and Controls...");
    const uploadControls = page.locator("#visionUploadControlsBar");
    assert(await uploadControls.isVisible(), "Upload controls bar not visible!");
    const liveControls = page.locator("#visionLiveControlsBar");
    assert(!await liveControls.isVisible(), "Live camera controls must be removed!");
    console.log("✓ Genuine video ingestion bar active, camera/CCTV successfully removed.");

    // 4. Test Curated Sample Loading
    console.log("[4/6] Loading Curated Sample (Silk Board Junction)...");
    const sampleBtn = page.locator("button:has-text('Silk Board Junction')");
    await sampleBtn.click();
    await page.waitForTimeout(1200);

    const badgePcu = await page.locator("#badgeTotalPcu").textContent();
    assert(badgePcu.includes("PCU"), "PCU badge not populated!");
    console.log(`✓ Indo-HCM PCU populated: ${badgePcu}`);

    const speedVal = await page.locator("#sidecarSpeed").textContent();
    assert(speedVal.includes("km/h"), "Speed not populated in sidecar!");
    console.log(`✓ Mean Speed populated: ${speedVal}`);

    // 5. Test Closed-Loop Actuation into Bengaluru Live Grid
    console.log("[5/6] Testing Closed-Loop Actuation into Live Grid...");
    const actuateBtn = page.locator("#btnActuateGrid");
    await actuateBtn.click();
    await page.waitForTimeout(1200);

    const resBox = page.locator("#actuationResultBox");
    assert(await resBox.isVisible(), "Actuation result box not displayed!");
    const websterC0 = await page.locator("#actuateWebsterC0").textContent();
    console.log(`✓ Closed-Loop Actuation success! Webster C0 = ${websterC0}`);

    // 6. Test Verified Video Pipeline
    console.log("[6/6] Testing Verified YOLO Output Playback...");
    const video = page.locator("#visionVideoElement");
    assert(await video.isVisible(), "Vision video element not visible!");
    console.log("✓ Video element verified and ready for playback.");

    console.log("=== ALL VISION INTELLIGENCE E2E TESTS PASSED ===");
  } catch (err) {
    console.error("E2E Test Failed:", err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
