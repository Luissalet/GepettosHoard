import { defineConfig } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const cache = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright');
const available = fs.existsSync(cache)
  ? fs
      .readdirSync(cache)
      .filter((x) => /^chromium-\d+$/.test(x))
      .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
      .map((x) => path.join(cache, x, 'chrome-win64/chrome.exe'))
      .find((x) => fs.existsSync(x))
  : undefined;
export default defineConfig({
  testDir: 'tests',
  testMatch: '*.spec.ts',
  workers: 1,
  timeout: 90000,
  use: {
    baseURL: 'http://127.0.0.1:5178',
    viewport: { width: 1440, height: 1000 },
    launchOptions: {
      executablePath: process.env.RELIEF_CHROME || available,
      args: ['--use-angle=d3d11'],
    },
  },
});
