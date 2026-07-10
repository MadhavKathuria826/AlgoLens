const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  try {
    console.log('Launching browser...');
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    
    console.log('Navigating to http://localhost:3000/...');
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle0', timeout: 30000 });
    
    console.log('Waiting for animations to settle...');
    await new Promise(resolve => setTimeout(resolve, 2500));
    
    const screenshotPath = 'C:\\Users\\hp\\.gemini\\antigravity-cli\\brain\\8d92afc3-4136-4b13-a45b-c5523e5147bb\\screenshot.png';
    console.log(`Saving screenshot to ${screenshotPath}...`);
    await page.screenshot({ path: screenshotPath });
    
    console.log('Done!');
    await browser.close();
  } catch (err) {
    console.error('Error occurred:', err);
    process.exit(1);
  }
})();
