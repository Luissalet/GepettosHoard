import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const root = path.join(process.env.LOCALAPPDATA, 'ms-playwright');
const executablePath = fs
  .readdirSync(root)
  .filter((x) => /^chromium-\d+$/.test(x))
  .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
  .map((x) => path.join(root, x, 'chrome-win64/chrome.exe'))
  .find(fs.existsSync);
const browser = await chromium.launch({ headless: true, executablePath });
const errors = [];
for (const [name, viewport] of [
  ['desktop', { width: 1440, height: 1000 }],
  ['mobile', { width: 390, height: 844 }],
]) {
  const page = await browser.newPage({ viewport });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('http://127.0.0.1:8766/?project=f78d90a8e7ab');
  await page.getByRole('button', { name: 'Interpretación', exact: true }).click();
  const section = page.getByRole('region', { name: 'Lectura de la geometría' });
  await section.getByRole('heading', { name: 'Qué entiende de la figura' }).waitFor();
  const summaries = section.locator('summary');
  await summaries.nth(0).click();
  await summaries.nth(5).click();
  await section.evaluate((element) => {
    const container = element.closest('.inspector-content');
    if (container && innerWidth > 680) {
      container.scrollTop +=
        element.getBoundingClientRect().top - container.getBoundingClientRect().top;
    }
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `.impeccable/review/scene-${name}.png`, fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1))
    throw Error('overflow ' + name);
  console.log(name, await summaries.count(), 'disclosures');
  await page.close();
}
await browser.close();
if (errors.length) throw Error(errors.join('\n'));
