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
  
  const captureTheme = async (themeName) => {
    // 1. Navigate to the page
    const url = `http://localhost:3000/studio?mock=min_edit_distance_2d&step=22`;
    console.log(`[Screenshot] Loading page for theme: ${themeName}`);
    await page.goto(url, { waitUntil: 'networkidle0' });
    
    // 2. Set the localStorage setting to force the UI mode
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
    
    // 3. Reload page to apply localStorage state
    console.log(`[Screenshot] Reloading page to apply theme...`);
    await page.reload({ waitUntil: 'networkidle0' });
    
    // 4. Wait for hydration
    await new Promise(r => setTimeout(r, 4000));
    
    // 5. Open the custom algorithm selector dropdown
    console.log(`[Screenshot] Opening custom algorithm selector dropdown...`);
    try {
      await page.waitForSelector('[data-testid="algorithm-selector"]', { timeout: 3000 });
      await page.click('[data-testid="algorithm-selector"]');
      // Wait for framer motion dropdown entrance animation
      await new Promise(r => setTimeout(r, 800));
    } catch (e) {
      console.warn(`[Screenshot] Failed to open algorithm selector:`, e.message);
    }
    
    // 6. Capture screenshot
    const filename = `studio_theme_${themeName}.png`;
    const destPath = path.join(brainDir, filename);
    await page.screenshot({ path: destPath });
    console.log(`[Screenshot] Saved theme ${themeName} screenshot to ${destPath}`);
  };
  
  try {
    await captureTheme('void');
    await captureTheme('slate');
    await captureTheme('obsidian');
  } catch (err) {
    console.error("Puppeteer capture failed:", err);
  } finally {
    await browser.close();
  }
}

run();
