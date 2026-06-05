import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const OUT = resolve(process.argv[2] || './images');
mkdirSync(OUT, { recursive: true });

const BASE = 'http://localhost:5173';
const VIEWPORT = { width: 1440, height: 900 };

const tabs = [
  { name: '01-live', label: 'Live' },
  { name: '02-escalations', label: 'Escalations' },
  { name: '03-occupancy', label: 'Occupancy' },
  { name: '04-luggage', label: 'Luggage' },
  { name: '05-system-health', label: 'System Health' },
  { name: '06-analytics', label: 'Analytics' },
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: VIEWPORT });
const page = await ctx.newPage();

await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

for (const tab of tabs) {
  console.log(`Capturing ${tab.label}...`);
  const link = page.getByRole('link', { name: new RegExp(`^${tab.label}`, 'i') });
  await link.first().click();
  await page.waitForTimeout(2000);
  const file = resolve(OUT, `${tab.name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  console.log(`  -> ${file}`);
}

await browser.close();
console.log('Done.');
