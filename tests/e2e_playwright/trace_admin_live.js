const { chromium } = require('playwright');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

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

  console.log('Logging in as traffic_admin...');
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  await page.fill('#usernameInput', 'traffic_admin');
  await page.fill('#passwordInput', 'Admin@123');
  await page.click('#submitBtn');
  await page.waitForNavigation({ timeout: 6000 }).catch(e => console.log('Nav:', e.message));
  await page.waitForTimeout(1500);

  console.log('Current URL:', page.url());
  const btnLive = await page.$('#tabConsoleLive');
  console.log('tabConsoleLive visible for traffic_admin:', await btnLive?.isVisible());

  await page.click('#tabConsoleLive');
  await page.waitForTimeout(1500);

  const viewLive = await page.$('#viewLiveSimulation');
  console.log('viewLive isVisible for admin:', await viewLive?.isVisible());
  const corridorItems = await page.$$('.live-corridor-item');
  console.log('Corridors rendered for admin:', corridorItems.length);

  console.log('Page errors:', pageErrors);
  console.log('Console logs:', consoleLogs.filter(l => l.type === 'error'));

  await browser.close();
})();
