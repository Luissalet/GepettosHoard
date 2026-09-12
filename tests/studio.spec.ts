import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
test.describe.configure({ mode: 'serial' });
let pid: string;
test.beforeAll(async () => {
  pid = JSON.parse(await fs.readFile('data/validation/project.json', 'utf8')).id;
  await fs.mkdir('.impeccable/review', { recursive: true });
});
test.beforeEach(async ({ page }) => {
  await page.addInitScript((id) => localStorage.setItem('relief-project', id), pid);
  await page.goto('/');
  await expect(page.locator('.view-status')).toContainText('UV vinculadas', { timeout: 60000 });
});

test('model selection links UV and exposes a persistent height editor', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.screenshot({ path: '.impeccable/review/desktop.png', fullPage: true });
  await page.locator('.region-row').nth(2).click();
  await expect(page.locator('.webgl canvas')).toHaveAttribute('data-ready-state', 'model:2');
  await expect(page.locator('.region-editor')).toBeInViewport();
  await page.screenshot({ path: '.impeccable/review/selection.png', fullPage: true });
  const slider = page.locator('.region-editor input[type=range]');
  const before = await slider.inputValue();
  const save = page.waitForResponse(
    (r) => r.request().method() === 'PATCH' && r.url().includes('/assets/'),
  );
  await slider.focus();
  await slider.press('End');
  expect((await save).status()).toBe(200);
  await expect(slider).toHaveValue('255');
  await page.getByRole('button', { name: 'Deshacer', exact: true }).click();
  await expect(slider).toHaveValue(before);
  await page.getByRole('button', { name: 'Textura UV', exact: true }).click();
  await page.getByLabel('Contenido de la vista').selectOption('ids');
  await page.getByRole('button', { name: 'Ver triangulación UV', exact: true }).click();
  await expect(page.locator('.uv-canvas-wrap canvas')).toBeVisible();
  await page.screenshot({ path: '.impeccable/review/uv.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('mobile retains canvas and controls without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Mostrar biblioteca' })).toBeVisible();
  await page.getByRole('button', { name: 'Interpretación', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({ path: '.impeccable/review/mobile.png', fullPage: true });
});

test('vision request includes actual 3D-to-UV samples and starts local inference', async ({
  page,
}) => {
  await page.getByRole('button', { name: 'Interpretación', exact: true }).click();
  const sent = page.waitForRequest((r) => r.url().endsWith('/analyze') && r.method() === 'POST');
  const response = page.waitForResponse((r) => r.url().endsWith('/analyze'));
  await page.getByRole('button', { name: 'Analizar modelo + UV', exact: true }).click();
  const request = await sent,
    payload = request.postDataJSON();
  expect(payload.views).toHaveLength(4);
  expect(
    payload.meshes.some((m: { regionSamples?: { samples: number }[] }) =>
      m.regionSamples?.some((r) => r.samples > 0),
    ),
  ).toBeTruthy();
  expect((await response).status()).toBe(200);
  await fs.writeFile(
    'data/validation/vision-job.json',
    JSON.stringify(await (await response).json(), null, 2),
  );
  await expect(page.locator('.analysis-progress')).toBeVisible();
  await page.screenshot({ path: '.impeccable/review/analysis.png', fullPage: true });
});
