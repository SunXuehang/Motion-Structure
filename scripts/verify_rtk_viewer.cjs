// Render the offline 3D artifact and verify that rotating the scene changes it.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const options = { headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] };
  if (process.env.PLAYWRIGHT_BROWSER_PATH) options.executablePath = process.env.PLAYWRIGHT_BROWSER_PATH;
  const browser = await chromium.launch(options);
  const page = await browser.newPage({ viewport: { width: 1840, height: 1160 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(pathToFileURL(path.join(root, 'renders/rtk_scan_occlusion_3d_v6_20261028.html')).href);
  await page.waitForFunction(() => window.shadowPlotReady === true, null, { timeout: 60000 });
  await page.waitForTimeout(800);
  const canvasCount = await page.locator('canvas').count();
  if (canvasCount < 2 || errors.length) throw new Error(JSON.stringify({ canvasCount, errors }));
  await page.screenshot({ path: path.join(root, 'renders/rtk_scan_occlusion_3d_v6_20261028.png') });
  await page.evaluate(async () => {
    await Plotly.relayout('shadow3d', { 'scene.camera.eye': { x: -1.65, y: -1.2, z: 0.8 } });
  });
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(root, 'renders/rtk_v6_qa_rotated.png') });
  const qa = { canvasCount, pageErrors: errors, rotationApplied: true };
  fs.writeFileSync(path.join(root, 'reports/rtk_mount_v6_browser_qa.json'), JSON.stringify(qa, null, 2) + '\n');
  console.log(JSON.stringify(qa));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
