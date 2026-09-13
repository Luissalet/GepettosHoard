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
const page = await browser.newPage();
const project = JSON.parse(fs.readFileSync('data/operations-validation/ui-project.json', 'utf8'));
const base = `http://127.0.0.1:8767/api/projects/${project.id}`;
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.goto(`http://127.0.0.1:8767/?project=${project.id}`);
await page.getByText('Guardar y versiones', { exact: true }).click();
await page
  .getByLabel('Nombre del proyecto', { exact: true })
  .fill('Prueba de recuperación · verificada');
const saved = page.waitForResponse(
  (r) => r.url().endsWith('/save') && r.request().method() === 'POST',
);
await page.getByLabel('Nombre del proyecto', { exact: true }).press('Control+s');
if ((await saved).status() !== 200) throw Error('Save failed');
await page.getByText('Versión guardada', { exact: true }).waitFor();
await page.getByText('Contraste del relieve', { exact: true }).click();
await page.getByLabel('Contraste del relieve', { exact: true }).fill('1.5');
const changed = page.waitForResponse((r) => r.url().endsWith('/contrast'));
await page.getByRole('button', { name: 'Aplicar a las alturas' }).click();
if ((await changed).status() !== 200) throw Error('Contrast failed');
const levels = async () => {
  const p = await (await fetch(base)).json();
  return p.assets[0].regions.map((r) => r.height).join(',');
};
if ((await levels()) !== '80,176') throw Error('Unexpected expanded levels');
const undo = page.waitForResponse((r) => r.url().endsWith('/restore'));
await page.getByRole('button', { name: 'Deshacer', exact: true }).click();
if ((await undo).status() !== 200 || (await levels()) !== '96,160') throw Error('Undo failed');
await page.reload();
const redo = page.waitForResponse((r) => r.url().endsWith('/restore'));
await page.getByRole('button', { name: 'Rehacer', exact: true }).click();
if ((await redo).status() !== 200 || (await levels()) !== '80,176')
  throw Error('Redo after reload failed');
await page.locator('.region-row').first().click();
const surfaceName = page.getByLabel('Nombre', { exact: true });
await surfaceName.fill('Superficie guardada al salir del campo');
const patched = page.waitForResponse((r) => r.request().method() === 'PATCH');
const bookmarked = page.waitForResponse(
  (r) => r.url().endsWith('/save') && r.request().method() === 'POST',
);
await surfaceName.press('Control+s');
if ((await patched).status() !== 200 || (await bookmarked).status() !== 200)
  throw Error('Pending edit and bookmark failed');
const current = await (await fetch(base)).json();
if (current.assets[0].regions[0].name !== 'Superficie guardada al salir del campo')
  throw Error('Bookmark did not wait for the field edit');
await browser.close();
if (errors.length) throw Error(errors.join('\n'));
console.log(
  'Real UI: Ctrl+S waits for field edits; contrast, undo, reload and persistent redo passed.',
);
