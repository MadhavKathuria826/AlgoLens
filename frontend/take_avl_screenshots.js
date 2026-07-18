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
    // 1. Delete Leaf (No Rebalance)
    await capture('avl_delete_leaf_no_rebalance', 98, 'avl_delete_leaf_pre.png');
    await capture('avl_delete_leaf_no_rebalance', 140, 'avl_delete_leaf_balanced.png');

    // 2. Delete One-Child (No Rebalance)
    await capture('avl_delete_one_child_no_rebalance', 158, 'avl_delete_one_child_pre.png');
    await capture('avl_delete_one_child_no_rebalance', 214, 'avl_delete_one_child_balanced.png');

    // 3. Delete Two-Child (No Rebalance)
    await capture('avl_delete_two_child_no_rebalance', 65, 'avl_delete_two_child_pre.png');
    await capture('avl_delete_two_child_no_rebalance', 72, 'avl_delete_two_child_swap.png');
    await capture('avl_delete_two_child_no_rebalance', 327, 'avl_delete_two_child_balanced.png');

    // 4. Delete Leaf (One Rotation)
    await capture('avl_delete_leaf_one_rotation', 45, 'avl_delete_one_rot_pre.png');
    await capture('avl_delete_leaf_one_rotation', 52, 'avl_delete_one_rot_trigger.png');
    await capture('avl_delete_leaf_one_rotation', 66, 'avl_delete_one_rot_balanced.png');

    // 5. Delete Cascade Rebalance
    await capture('avl_delete_cascade_rebalance', 335, 'avl_delete_cascade_pre.png');
    await capture('avl_delete_cascade_rebalance', 343, 'avl_delete_cascade_swap.png');
    await capture('avl_delete_cascade_rebalance', 346, 'avl_delete_cascade_rot1.png');
    await capture('avl_delete_cascade_rebalance', 367, 'avl_delete_cascade_rot2.png');
    await capture('avl_delete_cascade_rebalance', 405, 'avl_delete_cascade_balanced.png');

    // 6. Delete Root (Two-Child Swap)
    await capture('avl_delete_root', 29, 'avl_delete_root_pre.png');
    await capture('avl_delete_root', 33, 'avl_delete_root_swap.png');
    await capture('avl_delete_root', 44, 'avl_delete_root_balanced.png');

    // 7. Delete Heavy Child BF=0 (LL Rotation)
    await capture('avl_delete_heavy_child_zero', 65, 'avl_delete_bf0_pre.png');
    await capture('avl_delete_heavy_child_zero', 71, 'avl_delete_bf0_trigger.png');
    await capture('avl_delete_heavy_child_zero', 93, 'avl_delete_bf0_balanced.png');
  } catch (err) {
    console.error("Puppeteer capture failed:", err);
  } finally {
    await browser.close();
  }
}

run();
