const puppeteer = require('puppeteer');
const path = require('path');

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  
  const brainDir = 'C:\\Users\\hp\\.gemini\\antigravity-cli\\brain\\6e58f2d9-fede-4da2-8169-bcf6cee98aad';
  
  const capture = async (mockName, step, destFile) => {
    const url = `http://localhost:3000/studio?mock=${mockName}&step=${step}`;
    console.log(`Navigating to ${url}`);
    await page.goto(url, { waitUntil: 'networkidle0' });
    
    // Wait for animations and React hydration
    await new Promise(r => setTimeout(r, 6000));
    
    await page.screenshot({ path: path.join(brainDir, destFile) });
    console.log(`Saved screenshot to ${destFile}`);
  };
  
  try {
    // 1. LL Rotation
    await capture('avl_ll', 23, 'avl_ll_unbalanced.png');
    await capture('avl_ll', 39, 'avl_ll_balanced.png');

    // 2. RR Rotation
    await capture('avl_rr', 28, 'avl_rr_unbalanced.png');
    await capture('avl_rr', 39, 'avl_rr_balanced.png');

    // 3. LR Rotation
    await capture('avl_lr', 22, 'avl_lr_unbalanced.png');
    await capture('avl_lr', 39, 'avl_lr_mid.png');
    await capture('avl_lr', 49, 'avl_lr_balanced.png');

    // 4. RL Rotation
    await capture('avl_rl', 22, 'avl_rl_unbalanced.png');
    await capture('avl_rl', 39, 'avl_rl_mid.png');
    await capture('avl_rl', 49, 'avl_rl_balanced.png');

    // 5. No Rotation
    await capture('avl_balanced', 28, 'avl_no_rotation.png');

    // 6. Deep Sequence
    await capture('avl_deep', 221, 'avl_deep_balanced.png');
  } catch (err) {
    console.error("Puppeteer capture failed:", err);
  } finally {
    await browser.close();
  }
}

run();
