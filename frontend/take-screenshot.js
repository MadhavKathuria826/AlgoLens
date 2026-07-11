const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const delay = ms => new Promise(res => setTimeout(res, ms));

(async () => {
  let browser;
  try {
    console.log('Launching browser...');
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    const sizes = [
      { name: 'landing_375', width: 375, height: 667 },
      { name: 'landing_428', width: 428, height: 926 },
      { name: 'landing_768', width: 768, height: 1024 }
    ];

    for (const size of sizes) {
      console.log(`Setting viewport for ${size.name} (${size.width}x${size.height})...`);
      await page.setViewport({ width: size.width, height: size.height });
      
      console.log('Navigating to http://localhost:3000/...');
      await page.goto('http://localhost:3000/', { waitUntil: 'networkidle0', timeout: 30000 });
      
      console.log('Waiting for animations...');
      await delay(3000);
      
      const filePath = path.join('C:\\Users\\hp\\.gemini\\antigravity-cli\\brain\\81282edc-9b47-4180-9b3a-020f0af1fdf5', `${size.name}.png`);
      console.log(`Saving screenshot to ${filePath}...`);
      await page.screenshot({ path: filePath });
    }

    // Now test the gated Studio route
    console.log('Testing Gated Studio Route...');
    await page.setViewport({ width: 375, height: 667 });
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle0', timeout: 30000 });
    await delay(3000);
    
    // Find the Launch Studio button and click it
    console.log('Clicking Launch Studio button...');
    const buttons = await page.$$('button');
    let clicked = false;
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Launch Studio') || text.includes('Studio')) {
        console.log(`Found button with text: "${text}". Clicking it...`);
        await btn.click();
        clicked = true;
        break;
      }
    }

    if (!clicked) {
      console.log('Falling back to click...');
      await page.click('button');
    }

    console.log('Waiting for Studio route rendering/gating...');
    await delay(2000); 

    const filePath = path.join('C:\\Users\\hp\\.gemini\\antigravity-cli\\brain\\81282edc-9b47-4180-9b3a-020f0af1fdf5', 'gated_studio_375.png');
    console.log(`Saving gated studio screenshot to ${filePath}...`);
    await page.screenshot({ path: filePath });

    console.log('All screenshots captured successfully!');
  } catch (err) {
    console.error('Error during screenshot capture:', err);
  } finally {
    if (browser) {
      await browser.close();
    }
    process.exit(0);
  }
})();
