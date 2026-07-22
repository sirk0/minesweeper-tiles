// Generate the app icons for the TypeScript ("/next/") web app from a single
// vector source: a mine inside a steel-blue pentagon on a silver plate. The
// favicon ships as crisp SVG; the PWA/apple PNGs are rasterised from the same
// vector via headless Chromium (so edges stay clean).
//
//   web/public/favicon.svg            (vector, rounded plate)
//   web/public/icons/icon-192.png
//   web/public/icons/icon-512.png
//   web/public/icons/maskable-512.png (full-bleed, safe-zone motif)
//   web/public/apple-touch-icon.png   (full-bleed, iOS masks it)
//
// Run from web/:  node scripts/make-icons.mjs
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PUBLIC = resolve(dirname(fileURLToPath(import.meta.url)), "../public");

// The mine + pentagon motif, centred in a 512 viewBox. Reused at two scales:
// large for the favicon/standard icons, shrunk into the safe zone for maskable.
const motif = `
  <polygon points="256,81 422,202 359,398 153,398 90,202"
           fill="url(#pent)" stroke="#2a4c8e" stroke-width="8" stroke-linejoin="round"/>
  <g stroke="#141414" stroke-width="22" stroke-linecap="round">
    <line x1="164" y1="262" x2="348" y2="262"/>
    <line x1="256" y1="170" x2="256" y2="354"/>
    <line x1="191" y1="197" x2="321" y2="327"/>
    <line x1="191" y1="327" x2="321" y2="197"/>
  </g>
  <circle cx="256" cy="262" r="58" fill="#141414"/>
  <circle cx="235" cy="241" r="17" fill="#ffffff"/>`;

const defs = `
  <defs>
    <linearGradient id="plate" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#eef0f4"/><stop offset="1" stop-color="#c6cad2"/>
    </linearGradient>
    <linearGradient id="pent" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#6a94e0"/><stop offset="1" stop-color="#3a68b8"/>
    </linearGradient>
  </defs>`;

// Rounded silver plate with transparent corners — the browser-tab favicon and
// the standard (non-maskable) install icons.
const faviconSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">${defs}
  <rect x="26" y="26" width="460" height="460" rx="112" fill="url(#plate)" stroke="#969aa2" stroke-width="4"/>
  ${motif}
</svg>`;

// Full-bleed plate with the motif shrunk into the central safe zone — maskable
// and apple-touch, where the platform applies its own rounded mask.
const maskableSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">${defs}
  <rect width="512" height="512" fill="url(#plate)"/>
  <g transform="translate(256 256) scale(0.8) translate(-256 -256)">${motif}</g>
</svg>`;

async function render(browser, svg, size, out, transparent) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  const html = `<!doctype html><meta charset="utf-8">
    <style>*{margin:0;padding:0}html,body{width:${size}px;height:${size}px}
    svg{width:${size}px;height:${size}px;display:block}</style>${svg}`;
  await page.setContent(html, { waitUntil: "load" });
  mkdirSync(dirname(out), { recursive: true });
  await page.screenshot({ path: out, omitBackground: transparent });
  await page.close();
}

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;
const browser = await chromium.launch(
  executablePath ? { executablePath } : {},
);

writeFileSync(`${PUBLIC}/favicon.svg`, faviconSvg.trim() + "\n");
await render(browser, faviconSvg, 192, `${PUBLIC}/icons/icon-192.png`, true);
await render(browser, faviconSvg, 512, `${PUBLIC}/icons/icon-512.png`, true);
await render(browser, maskableSvg, 512, `${PUBLIC}/icons/maskable-512.png`, false);
await render(browser, maskableSvg, 180, `${PUBLIC}/apple-touch-icon.png`, false);
await browser.close();
console.log("icons written to", PUBLIC);
