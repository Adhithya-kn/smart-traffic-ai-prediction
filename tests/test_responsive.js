const { chromium } = require('playwright');
const path = require('path');

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
    await page.goto('http://127.0.0.1:8089/login');
    await page.fill('#usernameInput', 'commuter');
    await page.fill('#passwordInput', 'Admin@123');
    await page.click('#submitBtn');
    await page.waitForTimeout(1000);

    const btnLive = await page.$('#tabConsoleLive');
    const isVisible = await btnLive.isVisible();
    const box = await btnLive.boundingBox();
    console.log(`Viewport ${vp.name}: #tabConsoleLive isVisible = ${isVisible}, box:`, box);
    await page.screenshot({ path: path.join('/Users/ak/.gemini/antigravity/brain/8160a1e6-3892-4be7-b20e-f89f927e1df8/screenshots', `responsive_${vp.name}.png`) });
    await page.close();
  }

  await browser.close();
})();
