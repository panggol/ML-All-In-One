import { chromium } from 'playwright';

const TOKEN = process.argv[2];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.goto('http://localhost:3001/login');
  await page.waitForLoadState('networkidle');
  
  await page.evaluate((token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify({ username: 'admin', email: 'admin@test.com' }));
  }, TOKEN);
  
  await page.goto('http://localhost:3001/dashboard');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  
  await page.screenshot({ path: '/tmp/dashboard.png', fullPage: true });
  await browser.close();
  console.log('Screenshot saved');
})();
