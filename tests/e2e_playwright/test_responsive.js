const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || path.join(__dirname, 'screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const viewports = [
    { name: '1280px', width: 1280, height: 800 },
    { name: '1024px', width: 1024, height: 768 },
    { name: '800px', width: 800, height: 600 }
  ];

  for (const vp of viewports) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#usernameInput', 'commuter');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForTimeout(1000);

    const btnLive = await page.$('#tabConsoleLive');
    const isVisible = await btnLive.isVisible();
    const box = await btnLive.boundingBox();
    console.log(`Viewport ${vp.name}: #tabConsoleLive isVisible = ${isVisible}, box:`, box);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `responsive_${vp.name}.png`) });
    await page.close();
  }

  await browser.close();
})();
