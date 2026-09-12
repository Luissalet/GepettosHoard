import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { existsSync, readdirSync } from 'node:fs';
const sample = JSON.parse(await fs.readFile('data/validation/project.json', 'utf8'));
await fs.mkdir('.impeccable/review', { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.RELIEF_CHROME ||
    (process.env.LOCALAPPDATA &&
      (() => {
        const root = path.join(process.env.LOCALAPPDATA, 'ms-playwright');
        if (!existsSync(root)) return undefined;
        return readdirSync(root)
          .filter((x) => /^chromium-\d+$/.test(x))
          .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
          .map((x) => path.join(root, x, 'chrome-win64/chrome.exe'))
          .find(existsSync);
      })()) ||
    undefined,
  args: ['--use-angle=d3d11'],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text());
});
page.on('response', async (response) => {
  if (response.url().endsWith('/analyze')) {
    const data = await response.json();
    await fs.writeFile('data/validation/vision-job.json', JSON.stringify(data, null, 2));
    console.log('JOB', JSON.stringify(data));
  }
});
await page.addInitScript((id) => localStorage.setItem('relief-project', id), sample.id);
await page.goto('http://127.0.0.1:5178');
await page.waitForFunction(
  () => document.querySelector('.view-status')?.textContent?.includes('superficies'),
  { timeout: 60000 },
);
await page.screenshot({ path: '.impeccable/review/desktop.png', fullPage: true });
console.log('VIEW STATUS', await page.locator('.view-status').textContent());
await page.getByRole('button', { name: 'Textura UV', exact: true }).click();
await page.getByLabel('Contenido de la vista').selectOption('ids');
await page.getByRole('button', { name: 'Ver triangulación UV', exact: true }).click();
await page.locator('.region-row').first().click();
await page.waitForFunction(() => {
  const editor = document.querySelector('.region-editor');
  return editor && editor.getBoundingClientRect().top < innerHeight - 150;
});
await page.screenshot({ path: '.impeccable/review/uv.png', fullPage: true });
await page.getByRole('button', { name: 'Modelo 3D', exact: true }).click();
await page.screenshot({ path: '.impeccable/review/selection.png', fullPage: true });
await page.getByRole('button', { name: 'Interpretación', exact: true }).click();
await page.getByRole('button', { name: 'Analizar modelo + UV', exact: true }).click();
await page.waitForFunction(
  () => document.querySelector('.analysis-progress') || document.querySelector('.error-banner'),
  { timeout: 60000 },
);
console.log(
  'ANALYSIS',
  await page.locator('.error-banner').allTextContents(),
  await page.locator('.analysis-progress').allTextContents(),
);
await page.screenshot({ path: '.impeccable/review/analysis.png', fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: '.impeccable/review/mobile.png', fullPage: true });
console.log(
  'OVERFLOW',
  await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth })),
);
console.log('ERRORS', JSON.stringify(errors));
await fs.writeFile('data/validation/browser.json', JSON.stringify({ errors }, null, 2));
await browser.close();
