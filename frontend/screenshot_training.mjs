import { chromium } from 'playwright';

const CHROME_PATH = '/home/gem/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome';

async function main() {
  // Login first to get token
  const loginResp = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'sshot01', password: 'TestPass123!' })
  });
  const loginData = await loginResp.json();
  const token = loginData.access_token;
  console.log('Token obtained, length:', token.length);

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });

  const page = await context.newPage();
  
  // Log console messages
  page.on('console', msg => console.log('BROWSER:', msg.type(), msg.text()));

  // Go to login page first
  await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(2000);

  // Set localStorage token to bypass login
  await page.evaluate((t) => {
    localStorage.setItem('token', t);
    localStorage.setItem('user', JSON.stringify({ id: 3, username: 'sshot01', email: 'sshot01@test.com' }));
  }, token);
  console.log('Token set in localStorage');

  // Navigate to Training tab
  await page.goto('http://localhost:3000/training', { waitUntil: 'networkidle', timeout: 15000 });
  console.log('At training page');
  await page.waitForTimeout(3000);

  // Check URL
  console.log('Current URL:', page.url());

  // Check for visible content
  const heading = await page.locator('h2').first().textContent().catch(() => 'not found');
  console.log('First h2:', heading);

  // Take screenshot
  await page.screenshot({ path: '/tmp/training_tab_screenshot.png', fullPage: true });
  console.log('Screenshot saved to /tmp/training_tab_screenshot.png');

  await browser.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
