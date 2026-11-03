const { chromium } = require('playwright');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8089';
const SCREENSHOT_DIR = '/Users/ak/.gemini/antigravity/brain/7d9a74e9-a806-4e5f-bce6-a07b6456d3f9/screenshots';

async function runTest() {
  console.log('🚀 Running Playwright Bengaluru Events & Historical Disruption Verification...');
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,960']
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 960 }, deviceScaleFactor: 2 });

  console.log('--- 1. Testing Commuter Console Events ---');
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  await page.fill('#usernameInput', 'commuter');
  await page.fill('#passwordInput', 'Admin@123');
  await page.click('#submitBtn');
  await page.waitForURL('**/portal**', { timeout: 10000 });
  await page.waitForTimeout(600);

  const commuterEventCount = await page.locator('#eventsListContainer .event-item-card').count();
  console.log(`Commuter Active/Live Events visible: ${commuterEventCount}`);
  if (commuterEventCount === 0) throw new Error('No active events visible in commuter portal');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12_commuter_live_events.png'), fullPage: true });

  await page.click('#btnEventsHistorical');
  await page.waitForTimeout(600);
  const commuterHistCount = await page.locator('#eventsListContainer .event-item-card.historical').count();
  console.log(`Commuter Historical Events visible: ${commuterHistCount}`);
  if (commuterHistCount === 0) throw new Error('No historical events visible in commuter portal');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '13_commuter_historical_events.png'), fullPage: true });

  console.log('--- 2. Testing Authority Console Events ---');
  await page.click('#authBtn');
  await page.waitForURL('**/login**', { timeout: 5000 });
  await page.fill('#usernameInput', 'admin');
  await page.fill('#passwordInput', 'Admin@123');
  await page.click('#submitBtn');
  await page.waitForSelector('#authorityEventsQueueGrid', { timeout: 10000 });
  await page.waitForTimeout(600);

  const authActiveCount = await page.locator('#authorityEventsQueueGrid .authority-event-card').count();
  console.log(`Authority Active Disruptions visible: ${authActiveCount}`);
  if (authActiveCount === 0) throw new Error('No active disruptions visible in authority console');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '14_authority_active_disruptions.png'), fullPage: true });

  await page.click('#btnAuthEventsHistorical');
  await page.waitForTimeout(600);
  const authHistCount = await page.locator('#authorityEventsQueueGrid .authority-event-card').count();
  console.log(`Authority Historical Disruption Log visible: ${authHistCount}`);
  if (authHistCount === 0) throw new Error('No historical disruptions visible in authority console');
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '15_authority_historical_disruptions.png'), fullPage: true });

  await browser.close();
  console.log('✅ ALL BENGALURU RECENT, LIVE & HISTORICAL CONSOLE TESTS PASSED!');
}

runTest().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
