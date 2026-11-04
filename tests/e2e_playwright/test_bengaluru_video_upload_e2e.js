/**
 * tests/e2e_playwright/test_bengaluru_video_upload_e2e.js
 * End-to-End Browser Demonstration for 174 MB Bengaluru Traffic Video
 * Ingests Dataset/North-East.mp4, validates chunked upload progress, displays YOLO detections and HUD.
 */

const { chromium } = require('playwright');
const assert = require('assert');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8092';
const VIDEO_PATH = path.resolve(__dirname, "../../Dataset/North-East.mp4");

(async () => {
  console.log("================================================================================");
  console.log(" PLAYWRIGHT BROWSER E2E: BENGALURU 174 MB VIDEO INGESTION & PLAYBACK");
  console.log(` Target Server: ${BASE_URL}`);
  console.log(` Video Path:    ${VIDEO_PATH}`);
  console.log("================================================================================");

  assert(fs.existsSync(VIDEO_PATH), `Target video file missing at ${VIDEO_PATH}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(240000);

  try {
    // 1. Authenticate as Traffic Management Authority
    console.log("[1/6] Authenticating as Traffic Authority...");
    await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle", timeout: 15000 });
    await page.fill("#usernameInput", "traffic_admin");
    await page.fill("#passwordInput", "Admin@123");
    await page.click("#submitBtn");
    await page.waitForNavigation({ waitUntil: "networkidle", timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(1000);

    // 2. Open Vision AI Tab
    console.log("[2/6] Navigating to Vision AI Hub...");
    const visionTab = page.locator("#tabConsoleVision");
    assert(await visionTab.isVisible(), "Vision Tab navigation button missing!");
    await visionTab.click();
    await page.waitForTimeout(600);

    const visionView = page.locator("#viewVisionIntelligence");
    assert(await visionView.isVisible(), "Vision Intelligence viewport not visible!");
    console.log("  ✓ Vision AI viewport active.");

    // 3. Confirm Hardcoded Sample Buttons are Gone
    console.log("[3/6] Confirming Removal of Predefined Samples & CCTV...");
    assert(!await page.locator("button:has-text('Silk Board Junction')").isVisible());
    assert(!await page.locator("button:has-text('Outer Ring Road')").isVisible());
    assert(!await page.locator("button:has-text('MG Road Arterial')").isVisible());
    assert(!await page.locator("#visionLiveControlsBar").isVisible());
    console.log("  ✓ All hardcoded demonstration buttons and CCTV loops verified removed.");

    // 4. Select ~174 MB Bengaluru Traffic Video
    console.log("[4/6] Selecting 174 MB Bengaluru Traffic Video (Dataset/North-East.mp4)...");
    const fileInput = page.locator("#visionFileInput");
    await fileInput.setInputFiles(VIDEO_PATH);

    // 5. Monitor Chunked Upload Progress & Status Stages
    console.log("[5/6] Monitoring Real Upload Progress & Processing Status Stages...");
    const progressBarRow = page.locator("#visionProgressBarRow");
    await page.waitForTimeout(300);
    assert(await progressBarRow.isVisible(), "Progress bar must become visible upon selection!");

    let recordedProgress = [];
    const checkInterval = setInterval(async () => {
      try {
        const text = await page.locator("#visionProgressPercentText").textContent();
        const stage = await page.locator("#visionProgressStatusText").textContent();
        if (text && (!recordedProgress.length || recordedProgress[recordedProgress.length - 1].text !== text)) {
          recordedProgress.push({ text: text.trim(), stage: stage ? stage.trim() : "" });
          console.log(`  -> UI Progress: ${text.trim()} | Stage: ${stage ? stage.trim() : ""}`);
        }
      } catch (_) {}
    }, 500);

    // Await completion (up to 240 seconds for genuine 3,600-frame YOLO inference)
    console.log("  Awaiting complete genuine YOLO11n inference...");
    await page.waitForFunction(() => {
      const pcuText = document.getElementById("badgeTotalPcu")?.textContent || "";
      const rawCount = document.getElementById("kpiVisionRawCount")?.textContent || "";
      return pcuText.includes("PCU") && !pcuText.includes("0.0 PCU") && !rawCount.includes("--");
    }, null, { timeout: 240000 });

    clearInterval(checkInterval);

    // 6. Verify Results, Counts, PCU, and Video Playback
    console.log("[6/6] Verifying Actual Vehicle Counts, Indo-HCM PCU, and Video Playback...");
    const totalPcu = (await page.locator("#badgeTotalPcu").textContent()).trim();
    const rawVehicles = (await page.locator("#kpiVisionRawCount").textContent()).trim();
    const carCount = (await page.locator("#countCar").textContent()).trim();
    const motoCount = (await page.locator("#countMoto").textContent()).trim();
    const bicycleCount = (await page.locator("#countBicycle").textContent()).trim();
    const busCount = (await page.locator("#countBus").textContent()).trim();
    const truckCount = (await page.locator("#countTruck").textContent()).trim();
    const flowRate = (await page.locator("#kpiVisionFlow").textContent()).trim();

    console.log(`  ✓ Total Indo-HCM PCU:   ${totalPcu}`);
    console.log(`  ✓ Flow Rate:            ${flowRate}`);
    console.log(`  ✓ Unique Vehicles:      ${rawVehicles}`);
    console.log(`  ✓ Class Breakdown:      Cars: ${carCount} | Motorcycles: ${motoCount} | Bicycles: ${bicycleCount} | Buses: ${busCount} | Trucks: ${truckCount}`);

    assert(parseInt(carCount, 10) > 0, "Cars must be detected!");
    assert(parseInt(motoCount, 10) > 0, "Motorcycles must be detected!");
    assert(parseFloat(totalPcu) > 0, "PCU must be greater than zero!");

    const video = page.locator("#visionVideoElement");
    assert(await video.isVisible(), "Video player element must be visible!");
    const src = await video.getAttribute("src");
    assert(src && src.includes("/api/vision/video/"), `Video src must be streaming from API endpoint: ${src}`);
    console.log(`  ✓ Output Video Playback Stream: ${src}`);

    // Take verification screenshot of completed Vision AI dashboard
    const screenshotDir = path.resolve(__dirname, "screenshots");
    if (!fs.existsSync(screenshotDir)) fs.mkdirSync(screenshotDir, { recursive: true });
    const screenshotPath = path.join(screenshotDir, "bengaluru_cv_complete.png");
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`  ✓ Dashboard screenshot captured: ${screenshotPath}`);

    console.log("\n================================================================================");
    console.log(" 🎉 PLAYWRIGHT BROWSER DEMONSTRATION PASSED FLAWLESSLY!");
    console.log("================================================================================");
  } catch (err) {
    console.error("Playwright Demonstration Failed:", err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
