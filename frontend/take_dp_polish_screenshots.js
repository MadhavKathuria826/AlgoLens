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
    // Set Void theme
    console.log(`[Screenshot] Configuring local storage for Void theme...`);
    await page.goto('http://localhost:3000/studio', { waitUntil: 'networkidle0' });
    await page.evaluate(() => {
      const settings = JSON.parse(localStorage.getItem('algolens-settings') || '{}');
      settings.uiMode = 'void';
      localStorage.setItem('algolens-settings', JSON.stringify(settings));
    });
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2000));

    // ----------------------------------------------------
    // Test Case 1: Fibonacci @lru_cache (Memoization Cache Hit Pulse & Recurrence Display)
    // ----------------------------------------------------
    console.log(`[Screenshot] Running Case 1: Fibonacci @lru_cache...`);
    const fibCode = `from functools import lru_cache

@lru_cache(maxsize=None)
def fibonacci(n):
    if n <= 1: return n
    return fibonacci(n-1) + fibonacci(n-2)

fibonacci(10)
`;
    await page.evaluate((code) => {
      if (window.setStudioCode) {
        window.setStudioCode(code);
      }
    }, fibCode);
    
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 11 times to reach Step 11 (cache hit for key 1)
    console.log(`[Screenshot] Stepping forward to trigger cache hit...`);
    for (let i = 0; i < 11; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 200));
    }
    
    const fibPath = path.join(brainDir, 'studio_memo_fibonacci_pulse.png');
    await page.screenshot({ path: fibPath });
    console.log(`[Screenshot] Case 1 saved to ${fibPath}`);

    // ----------------------------------------------------
    // Test Case 2: Min Edit Distance Tabulated (2D Recurrence Text Display)
    // ----------------------------------------------------
    console.log(`[Screenshot] Running Case 2: Min Edit Distance Tabulation...`);
    const editCode = `def min_edit_distance(word1, word2):
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): dp[i][0] = i
    for j in range(n + 1): dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i-1] == word2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[m][n]

min_edit_distance("horse", "ros")
`;
    await page.evaluate((code) => {
      if (window.setStudioCode) {
        window.setStudioCode(code);
      }
    }, editCode);
    
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 10 times to display initial cells and active recurrence
    for (let i = 0; i < 10; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 200));
    }
    
    const editPath = path.join(brainDir, 'studio_tab_edit_distance_recurrence.png');
    await page.screenshot({ path: editPath });
    console.log(`[Screenshot] Case 2 saved to ${editPath}`);

    // ----------------------------------------------------
    // Test Case 3: Custom DP (Coin Change recursive memoized cache pulse + recurrence display)
    // ----------------------------------------------------
    console.log(`[Screenshot] Running Case 3: Coin Change recursive memoized...`);
    const coinsCode = `memo = {}
def coin_change(coins, amount):
    if amount in memo:
        return memo[amount]
    if amount == 0:
        return 0
    if amount < 0:
        return -1
    min_coins = float('inf')
    for coin in coins:
        res = coin_change(coins, amount - coin)
        if res >= 0:
            min_coins = min(min_coins, res + 1)
    memo[amount] = min_coins if min_coins != float('inf') else -1
    return memo[amount]

coin_change([1, 2, 5], 6)
`;
    await page.evaluate((code) => {
      if (window.setStudioCode) {
        window.setStudioCode(code);
      }
    }, coinsCode);
    
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 18 times to trigger cache hit lookups on coin amount subproblems
    console.log(`[Screenshot] Stepping forward to coin change cache hit...`);
    for (let i = 0; i < 18; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 200));
    }
    
    const coinsPath = path.join(brainDir, 'studio_coin_change_memo.png');
    await page.screenshot({ path: coinsPath });
    console.log(`[Screenshot] Case 3 saved to ${coinsPath}`);
    
  } catch (err) {
    console.error("Puppeteer capture failed:", err);
  } finally {
    await browser.close();
  }
}

run();
