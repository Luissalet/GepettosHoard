import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const root = path.join(process.env.LOCALAPPDATA, 'ms-playwright');
const executablePath = fs
  .readdirSync(root)
  .filter((x) => /^chromium-\d+$/.test(x))
  .sort((a, b) => +b.split('-')[1] - a.split('-')[1])
  .map((x) => path.join(root, x, 'chrome-win64/chrome.exe'))
  .find(fs.existsSync);
const browser = await chromium.launch({ headless: true, executablePath });
const errors = [];
for (const [label, viewport] of [
  ['desktop', { width: 1440, height: 1000 }],
  ['mobile', { width: 390, height: 844 }],
]) {
  const page = await browser.newPage({ viewport });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('http://127.0.0.1:8767/?project=f78d90a8e7ab');
  await page.getByRole('button', { name: 'Equipo y lotes', exact: true }).click();
  await page.locator('.gpu-row').first().waitFor();
  await page.waitForFunction(
    () => document.querySelector('.operations-machine select')?.value.length > 0,
  );
  await page
    .getByText('El modelo seleccionado está cargado en memoria.', { exact: true })
    .waitFor();
  if ((await page.locator('.gpu-row').count()) !== 3) throw Error('Missing GPU readings');
  await page.screenshot({ path: `.impeccable/review/operations-${label}.png`, fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1))
    throw Error(label + ' overflow');
  await page.getByRole('button', { name: 'Volver al taller' }).click();
  await page.getByText('Contraste del relieve', { exact: true }).click();
  await page.getByLabel('Contraste del relieve', { exact: true }).fill('1.2');
  await page.getByRole('button', { name: 'Aplicar a las alturas' }).waitFor();
  await page.close();
}
await browser.close();
if (errors.length) throw Error(errors.join('\n'));
console.log(
  'Operations UI: desktop/mobile, 3 GPUs, workshop return and contrast controls verified.',
);
