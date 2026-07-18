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
  
  // Helper to force theme settings
  const applyThemeSettings = async (themeName) => {
    await page.evaluate((theme) => {
      const defaultSettings = {
        uiMode: theme,
        editorTheme: 'vs-dark',
        graphicsQuality: 'balanced',
        maxRecursionDepth: 1000,
        executionTimeoutMs: 10000,
        animationSpeed: 'normal',
        autoRunOnPaste: false,
        showValueLabels: true,
        showIndexAnnotations: true,
        nodeSize: 'medium',
        colorBlindSafe: false,
        reducedMotion: false,
        textSize: 'default',
      };
      localStorage.setItem('algolens-settings', JSON.stringify(defaultSettings));
    }, themeName);
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 3000));
  };
  
  try {
    // ----------------------------------------------------
    // CASE 1: Bubble Sort (Condition Evaluation) under Void Theme
    // ----------------------------------------------------
    console.log(`[Screenshot] Loading Studio for Bubble Sort (Void Theme)...`);
    await page.goto('http://localhost:3000/studio', { waitUntil: 'networkidle0' });
    await applyThemeSettings('void');
    
    console.log(`[Screenshot] Clicking Run for Bubble Sort...`);
    await page.waitForSelector('[data-testid="run-button"]', { timeout: 3000 });
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 7 times to reach the comparison line execution step
    console.log(`[Screenshot] Stepping forward to the first active comparison...`);
    for (let i = 0; i < 7; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 300));
    }
    
    // Capture Bubble Sort Void theme screenshot
    const pathVoid = path.join(brainDir, 'studio_theme_void.png');
    await page.screenshot({ path: pathVoid });
    console.log(`[Screenshot] Saved Bubble Sort screenshot to ${pathVoid}`);
    
    // ----------------------------------------------------
    // CASE 2: Linear Search (Pasted Custom Code) under Slate Theme
    // ----------------------------------------------------
    console.log(`[Screenshot] Injecting Linear Search code (Slate Theme)...`);
    await applyThemeSettings('slate');
    
    const linearSearchCode = `def linear_search(arr, target):
    for val in arr:
        if val == target:
            return True
    return False

linear_search([10, 20, 30, 40], 30)
`;
    await page.evaluate((code) => {
      if (window.setStudioCode) {
        window.setStudioCode(code);
      }
    }, linearSearchCode);
    
    console.log(`[Screenshot] Clicking Run for Linear Search...`);
    await page.waitForSelector('[data-testid="run-button"]', { timeout: 3000 });
    await page.click('[data-testid="run-button"]');
    await new Promise(r => setTimeout(r, 6000));
    
    // Step forward 3 times to trigger the matched condition (30 == 30?)
    console.log(`[Screenshot] Stepping forward to target condition evaluation...`);
    for (let i = 0; i < 3; i++) {
      await page.waitForSelector('[data-testid="next-button"]', { timeout: 2000 });
      await page.click('[data-testid="next-button"]');
      await new Promise(r => setTimeout(r, 300));
    }
    
    // Capture Linear Search Slate theme screenshot
    const pathSlate = path.join(brainDir, 'studio_theme_slate.png');
    await page.screenshot({ path: pathSlate });
    console.log(`[Screenshot] Saved Linear Search screenshot to ${pathSlate}`);
    
    // ----------------------------------------------------
    // CASE 3: Obsidian Theme Workspace
    // ----------------------------------------------------
    console.log(`[Screenshot] Capturing Obsidian Theme screenshot...`);
    await applyThemeSettings('obsidian');
    
    const pathObsidian = path.join(brainDir, 'studio_theme_obsidian.png');
    await page.screenshot({ path: pathObsidian });
    console.log(`[Screenshot] Saved Obsidian screenshot to ${pathObsidian}`);
    
  } catch (err) {
    console.error("Puppeteer capture failed:", err);
  } finally {
    await browser.close();
  }
}

run();
