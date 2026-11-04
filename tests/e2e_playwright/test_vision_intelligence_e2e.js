/**
 * tests/e2e_playwright/test_vision_intelligence_e2e.js
 * End-to-End Playwright Verification for AI Vision Intelligence & Genuine Chunked Upload.
 */

const { chromium } = require('playwright');
const assert = require('assert');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8092';

(async () => {
  console.log("=== Starting Vision Intelligence E2E Audit ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // 1. Authenticate as Traffic Management Admin
    console.log("[1/6] Authenticating as Traffic Authority...");
    await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle", timeout: 15000 });
    await page.fill("#usernameInput", "traffic_admin");
    await page.fill("#passwordInput", "Admin@123");
    await page.click("#submitBtn");
    await page.waitForNavigation({ waitUntil: "networkidle", timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(1000);

    // 2. Click Vision AI Tab
    console.log("[2/6] Switching to Vision AI Tab...");
    const visionTab = page.locator("#tabConsoleVision");
    assert(await visionTab.isVisible(), "Vision tab button not found in navigation!");
    await visionTab.click();
    await page.waitForTimeout(600);

    const visionView = page.locator("#viewVisionIntelligence");
    assert(await visionView.isVisible(), "Vision Intelligence Viewport failed to display!");
    console.log("✓ Vision Intelligence Viewport active and visible.");

    // 3. Verify Removal of Hardcoded Samples & CCTV Controls
    console.log("[3/6] Verifying Removal of Hardcoded Sample Demonstrations & CCTV...");
    const silkBoardBtn = page.locator("button:has-text('Silk Board Junction')");
    assert(!await silkBoardBtn.isVisible(), "Forbidden sample button 'Silk Board Junction' must not exist!");
    const orrBtn = page.locator("button:has-text('Outer Ring Road')");
    assert(!await orrBtn.isVisible(), "Forbidden sample button 'Outer Ring Road' must not exist!");
    const mgRoadBtn = page.locator("button:has-text('MG Road Arterial')");
    assert(!await mgRoadBtn.isVisible(), "Forbidden sample button 'MG Road Arterial' must not exist!");
    const liveControls = page.locator("#visionLiveControlsBar");
    assert(!await liveControls.isVisible(), "Live camera/CCTV controls must be removed!");
    console.log("✓ Curated sample buttons and live camera controls verified removed.");

    // 4. Test Video Ingestion Dropzone & Genuine File Selection
    console.log("[4/6] Ingesting Video File via Chunked Upload Dropzone...");
    const uploadControls = page.locator("#visionUploadControlsBar");
    assert(await uploadControls.isVisible(), "Upload controls bar not visible!");

    const testVideoPath = path.resolve(__dirname, "../../app/static/sample_traffic.mp4");
    const fileInput = page.locator("#visionFileInput");
    await fileInput.setInputFiles(testVideoPath);

    // 5. Monitor Real Upload & YOLO Progress
    console.log("[5/6] Monitoring Real Upload Progress & Genuine YOLO Processing...");
    const progressBarRow = page.locator("#visionProgressBarRow");
    await page.waitForTimeout(500);

    // Wait for progress row to be displayed and job to proceed
    const isProgressVisible = await progressBarRow.isVisible();
    assert(isProgressVisible, "Progress bar row must be visible during ingestion!");

    // Await completion (status text or result badges)
    console.log("  Waiting for YOLO inference completion...");
    await page.waitForFunction(() => {
      const pcuText = document.getElementById("badgeTotalPcu")?.textContent || "";
      const rawCount = document.getElementById("kpiVisionRawCount")?.textContent || "";
      return pcuText.includes("PCU") && !pcuText.includes("0.0 PCU") && !rawCount.includes("--");
    }, { timeout: 60000 });

    const badgePcu = await page.locator("#badgeTotalPcu").textContent();
    const rawCount = await page.locator("#kpiVisionRawCount").textContent();
    const carCount = await page.locator("#countCar").textContent();
    const motoCount = await page.locator("#countMoto").textContent();
    const busCount = await page.locator("#countBus").textContent();
    const truckCount = await page.locator("#countTruck").textContent();
    const bicycleCount = await page.locator("#countBicycle").textContent();

    console.log(`✓ Real Indo-HCM PCU populated: ${badgePcu.trim()}`);
    console.log(`✓ Real Raw Vehicles: ${rawCount.trim()}`);
    console.log(`✓ Class Breakdown - Cars: ${carCount}, Two-Wheelers: ${motoCount}, Buses: ${busCount}, Trucks: ${truckCount}, Bicycles: ${bicycleCount}`);

    assert(parseInt(carCount, 10) >= 0, "Car count must be a non-negative integer!");

    // 6. Test Verified Output Video Playback
    console.log("[6/6] Testing Annotated YOLO Output Video Element & Stream...");
    const video = page.locator("#visionVideoElement");
    assert(await video.isVisible(), "Vision video element not visible!");
    const videoSrc = await video.getAttribute("src");
    assert(videoSrc && videoSrc.includes("/api/vision/video/"), `Video src must point to video API stream, got: ${videoSrc}`);
    console.log(`✓ Output video stream URL: ${videoSrc}`);

    console.log("=== ALL VISION INTELLIGENCE E2E TESTS PASSED SUCCESSFULLY ===");
  } catch (err) {
    console.error("E2E Test Failed:", err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
