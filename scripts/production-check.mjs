// Read-only check of the built app, including the project created by Blender.
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const cache = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright');
const executablePath =
  process.env.RELIEF_CHROME ||
  fs
    .readdirSync(cache)
    .filter((x) => /^chromium-\d+$/.test(x))
    .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
    .map((x) => path.join(cache, x, 'chrome-win64/chrome.exe'))
    .find((x) => fs.existsSync(x));
const browser = await chromium.launch({
  headless: true,
  executablePath,
  args: ['--use-angle=d3d11'],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
const primary = JSON.parse(fs.readFileSync('data/validation/project.json', 'utf8')).id;
const sent = JSON.parse(
  fs.readFileSync('data/validation/blender-send-report.json', 'utf8'),
).project;
const results = [];
for (const pid of [sent, primary]) {
  await page.goto(`http://127.0.0.1:8766/?project=${pid}`);
  await page.waitForFunction(
    () => /superficies|No se pudo/.test(document.querySelector('.view-status')?.textContent || ''),
    null,
    { timeout: 60000 },
  );
  const status = await page.locator('.view-status').textContent();
  if (!status?.includes('UV vinculadas')) {
    await page.screenshot({ path: '.impeccable/review/production-error.png', fullPage: true });
    throw new Error(JSON.stringify({ pid, status, errors }));
  }
  results.push({ project: pid, status: await page.locator('.view-status').textContent() });
}
await page.screenshot({ path: '.impeccable/review/production.png', fullPage: true });
if (errors.length) throw new Error(errors.join('\n'));
fs.writeFileSync(
  'data/validation/production-report.json',
  JSON.stringify({ result: 'passed', projects: results, errors }, null, 2),
);
console.log(JSON.stringify(results));
await browser.close();
