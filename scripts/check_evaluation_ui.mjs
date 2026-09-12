import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const cache = path.join(process.env.LOCALAPPDATA, 'ms-playwright');
const executablePath = fs
  .readdirSync(cache)
  .filter((x) => /^chromium-\d+$/.test(x))
  .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
  .map((x) => path.join(cache, x, 'chrome-win64/chrome.exe'))
  .find((x) => fs.existsSync(x));
const browser = await chromium.launch({ headless: true, executablePath });
const errors = [];
for (const [name, size, project, detail] of [
  ['desktop', { width: 1440, height: 1000 }, 'f78d90a8e7ab', 'detail-front'],
  ['mobile', { width: 390, height: 844 }, 'cb3854e493f6', 'detail-back'],
]) {
  const page = await browser.newPage({ viewport: size });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`http://127.0.0.1:8766/?project=${project}`);
  await page.getByRole('button', { name: 'Relieve real', exact: true }).click();
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll('.compare-images img')].length === 2 &&
      [...document.querySelectorAll('.compare-images img')].every(
        (x) => x.complete && x.naturalWidth > 0,
      ),
  );
  if (await page.getByLabel('Etapa del resultado').count()) {
    await page.getByLabel('Ángulo del relieve').selectOption('back');
    await page.waitForFunction(() =>
      [...document.querySelectorAll('.compare-images img')].every(
        (x) => x.complete && x.naturalWidth > 0,
      ),
    );
    if (
      !(await page
        .locator('.compare-images img')
        .first()
        .getAttribute('src')
        .then((s) => s.includes('finished-back')))
    )
      throw Error('Missing finished stage');
    await page.getByRole('link', { name: 'Descargar STL unido' }).waitFor();
    await page.getByLabel('Etapa del resultado').selectOption('editable');
  }
  await page.getByLabel('Referencia de comparación').selectOption('original');
  await page.getByLabel('Ángulo del relieve').selectOption(detail);
  await page.getByLabel('Comparar antes y después').fill('40');
  await page.waitForFunction(() =>
    [...document.querySelectorAll('.compare-images img')].every(
      (x) => x.complete && x.naturalWidth > 0,
    ),
  );
  await page.screenshot({ path: `.impeccable/review/evaluation-${name}.png`, fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1))
    throw Error(name + ' has horizontal overflow');
  await page.close();
}
await browser.close();
if (errors.length) throw Error(errors.join('\n'));
console.log(
  'Desktop/mobile comparison loaded; controls work; no page errors or horizontal overflow.',
);
