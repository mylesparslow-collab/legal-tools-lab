// Render a statement HTML file to a PNG (US Letter proportions) and a PDF (US Letter).
// Usage: node scripts/render_page.js <statement.html> <out.png> <out.pdf>
// Needs Playwright with Chromium already installed. Makes no network requests.
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [html, png, pdf] = process.argv.slice(2);
  if (!html || !png || !pdf) {
    console.error('usage: node scripts/render_page.js <statement.html> <out.png> <out.pdf>');
    process.exit(2);
  }
  const browser = await chromium.launch();
  // 8.5in x 11in at 96 px per inch, plus the grey margin around the sheet on screen.
  const page = await browser.newPage({ viewport: { width: 864, height: 1104 }, deviceScaleFactor: 2 });
  await page.goto('file://' + path.resolve(html));
  const sheet = page.locator('.sheet');
  const box = await sheet.boundingBox();
  await sheet.screenshot({ path: png });
  await page.pdf({ path: pdf, format: 'Letter', printBackground: true, preferCSSPageSize: true });
  await browser.close();
  // Sheet height in inches on screen: above 11 means the content does not fit one page.
  console.log(JSON.stringify({ sheet_height_in: +(box.height / 96).toFixed(3) }));
})().catch((err) => { console.error(String(err)); process.exit(1); });
