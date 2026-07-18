const puppeteer = require('puppeteer');
const path = require('path');

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  
  const brainDir = 'C:\\Users\\hp\\.gemini\\antigravity-cli\\brain\\a4a36264-e030-429b-b724-cce22309e48a';
  
  try {
    // ----------------------------------------------------
    // Bug 1 Verification: Fibonacci(10) final tabulation showing dp[1] = 1
    // ----------------------------------------------------
    console.log(`[Screenshot] Loading Studio for Fibonacci(10)...`);
    await page.goto('http://localhost:3000/studio', { waitUntil: 'networkidle0' });
    
    // Set Void theme
    await page.evaluate(() => {
      const settings = JSON.parse(localStorage.getItem('algolens-settings') || '{}');
      settings.uiMode = 'void';
      localStorage.setItem('algolens-settings', JSON.stringify(settings));
    });
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2000));
    
    const fibCode = `def fibonacci(n):
    if n <= 0: return 0
    if n == 1: return 1
    dp = [0] * (n + 1)
    dp[0] = 0
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]

fibonacci(10)
`;
    await page.evaluate((code) => {
      if (window.setStudioCode) {
        window.setStudioCode(code);
      }
    }, fibCode);
    
    console.log(`[Screenshot] Running Fibonacci(10)...`);
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 26 times to execute to final step
    console.log(`[Screenshot] Stepping to the end step to see full DP array...`);
    for (let i = 0; i < 26; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 200));
    }
    
    const fibPath = path.join(brainDir, 'studio_fibonacci_dp1.png');
    await page.screenshot({ path: fibPath });
    console.log(`[Screenshot] Saved Fibonacci(10) screenshot to ${fibPath}`);
    
    // ----------------------------------------------------
    // Bug 2 Verification: Fibonacci(30) scrolling timeline
    // ----------------------------------------------------
    console.log(`[Screenshot] Injecting Fibonacci(30) for timeline scroll verification...`);
    const longFibCode = `def fibonacci(n):
    if n <= 0: return 0
    if n == 1: return 1
    dp = [0] * (n + 1)
    dp[0] = 0
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]

fibonacci(30)
`;
    await page.evaluate((code) => {
      if (window.setStudioCode) {
        window.setStudioCode(code);
      }
    }, longFibCode);
    
    console.log(`[Screenshot] Running Fibonacci(30)...`);
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 60 times. This will scroll the active step bar into view.
    console.log(`[Screenshot] Stepping forward 60 times to scroll timeline...`);
    for (let i = 0; i < 60; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 150));
    }
    
    const timelinePath = path.join(brainDir, 'studio_timeline_seek.png');
    await page.screenshot({ path: timelinePath });
    console.log(`[Screenshot] Saved Timeline scroll screenshot to ${timelinePath}`);
    
  } catch (err) {
    console.error("Puppeteer capture failed:", err);
  } finally {
    await browser.close();
  }
}

run();
