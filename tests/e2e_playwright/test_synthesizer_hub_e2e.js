/**
 * tests/e2e_playwright/test_synthesizer_hub_e2e.js
 * End-to-End Playwright Verification for API & System Synthesizer Hub,
 * Multi-Subsystem Handshake, Atomic POSIX Storage Snapshots, and 4-way Navigation.
 */

const { chromium } = require('playwright');
const assert = require('assert');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

(async () => {
  console.log("===============================================================");
  console.log("🚀 STARTING API & SYSTEM SYNTHESIZER HUB E2E PLAYWRIGHT AUDIT");
  console.log("===============================================================");

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

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // 1. Sign In as Admin
    console.log("[1/7] Signing In as Administrator...");
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.fill('#usernameInput', 'admin');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForNavigation({ timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(1000);

    const userBadge = await page.textContent('#userBadge');
    assert(userBadge.includes('admin'), `Expected admin user badge, got: ${userBadge}`);
    console.log(`✓ Admin session authenticated: ${userBadge.trim()}`);

    // 2. Switch to API & System Synthesizer Tab
    console.log("[2/7] Switching to API & System Synthesizer Hub...");
    const synthTab = page.locator('#tabConsoleSynthesizer');
    assert(await synthTab.isVisible(), "Synthesizer tab button not visible in header switcher!");
    await synthTab.click();
    await page.waitForTimeout(800);

    const synthView = page.locator('#viewSynthesizer');
    assert(await synthView.isVisible(), "Synthesizer viewport failed to display!");
    console.log("✓ API & System Synthesizer Hub viewport active and rendered.");

    // 3. Multi-Subsystem Handshake Probe
    console.log("[3/7] Probing Multi-Subsystem Handshake...");
    const btnHandshake = page.locator('#btnRunSynthesizerHandshake');
    await btnHandshake.click();
    await page.waitForTimeout(1800);

    const overallBadge = await page.locator('#synOverallHealthBadge').textContent();
    assert(overallBadge.includes('OPTIMAL') || overallBadge.includes('DEGRADED') || overallBadge.includes('Healthy'), `Overall health status unexpected: ${overallBadge}`);
    const kpiHealth = await page.locator('#kpiSynHealthStatus').textContent();
    console.log(`✓ Handshake verified: Badge = ${overallBadge.trim()}, KPI = ${kpiHealth.trim()}`);

    // 4. POSIX Atomic Storage Durability & Snapshot Creation
    console.log("[4/7] Testing POSIX Atomic Storage & Snapshot Capture...");
    const durabilityVal = await page.locator('#synDurabilityBadge').textContent();
    assert(durabilityVal.includes('F_FULLFSYNC') || durabilityVal.includes('Atomic'), `Storage durability not verified: ${durabilityVal}`);
    console.log(`✓ Storage Durability Verified: ${durabilityVal.trim()}`);

    await page.fill('#synSnapshotNoteInput', 'E2E Playwright Automated Test Snapshot');
    const btnBackup = page.locator('button:has-text("Create Atomic Snapshot")');
    await btnBackup.click();
    await page.waitForTimeout(1800);

    const tableBody = await page.locator('#synSnapshotsTableBody').textContent();
    assert(tableBody.includes('snapshot_'), "Snapshot entry not listed in snapshots table!");
    console.log("✓ Atomic snapshot backup created and registered in catalog table.");

    // 5. Calibrated Non-Linear Perturbation Stream Generation
    console.log("[5/7] Generating Synthetic Stress Stream (Monsoon Deluge)...");
    await page.selectOption('#synScenarioSelect', 'monsoon_flood');
    const btnGenStream = page.locator('button:has-text("Synthesize Scenario Stream")');
    await btnGenStream.click();
    await page.waitForTimeout(1200);

    const streamContainer = page.locator('#synStreamOutputContainer');
    assert(await streamContainer.isVisible(), "Synthetic stream output container not visible!");
    const stressVal = await page.locator('#synStreamStress').textContent();
    const speedDrop = await page.locator('#synStreamSpeedDrop').textContent();
    console.log(`✓ Non-linear stream generated: Grid Stress = ${stressVal.trim()}, Speed Drop = ${speedDrop.trim()}`);

    // 6. Dynamic Machine Learning Prediction Sandbox
    console.log("[6/7] Evaluating ML Inference Sandbox...");
    await page.fill('#synSandboxVolume', '3200');
    await page.locator('#synSandboxVolume').dispatchEvent('input');
    await page.waitForTimeout(600);

    const sandboxBadge = await page.locator('#synSandboxPredBadge').textContent();
    const marginVal = await page.locator('#synSandboxMargin').textContent();
    const entropyVal = await page.locator('#synSandboxEntropy').textContent();
    assert(sandboxBadge.length > 0, "Predicted class empty!");
    console.log(`✓ Inference Sandbox: Class = ${sandboxBadge.trim()}, Margin = ${marginVal.trim()}, Entropy = ${entropyVal.trim()}`);

    // 7. Full 4-Way Navigation Cycle
    console.log("[7/7] Testing 4-Way Full Cycle Navigation Integrity...");
    // Live Simulation
    await page.locator('#tabConsoleLive').click();
    await page.waitForTimeout(400);
    assert(await page.locator('#viewLiveSimulation').isVisible(), "Live simulation viewport failed!");
    assert(!await page.locator('#viewSynthesizer').isVisible(), "Synthesizer viewport leaked into Live!");

    // Vision Intelligence
    await page.locator('#tabConsoleVision').click();
    await page.waitForTimeout(400);
    assert(await page.locator('#viewVisionIntelligence').isVisible(), "Vision viewport failed!");
    assert(!await page.locator('#viewLiveSimulation').isVisible(), "Live viewport leaked into Vision!");

    // Standard Portal (Authority)
    await page.locator('#tabConsoleStandard').click();
    await page.waitForTimeout(400);
    assert(await page.locator('#viewAuthority').isVisible(), "Authority viewport failed!");
    assert(!await page.locator('#viewVisionIntelligence').isVisible(), "Vision viewport leaked into Standard!");

    // Synthesizer
    await page.locator('#tabConsoleSynthesizer').click();
    await page.waitForTimeout(400);
    assert(await page.locator('#viewSynthesizer').isVisible(), "Synthesizer viewport failed to re-open!");

    console.log("✓ Full 4-way navigation cycle clean with zero DOM leaks or collision.");
    assert(consoleErrors.length === 0, `Detected browser console errors: ${consoleErrors.join(', ')}`);

    console.log("===============================================================");
    console.log("🎉 ALL SYNTHESIZER HUB E2E PLAYWRIGHT TESTS PASSED FLAWLESSLY!");
    console.log("===============================================================");
  } catch (err) {
    console.error("❌ E2E Playwright Synthesizer Audit Failed:", err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
