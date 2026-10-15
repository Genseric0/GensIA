// Optional development tool. Never installs packages or browsers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function validateMetrics(m) {
  assert.equal(m.cards, 4, 'Expected four agent cards');
  assert.equal(m.notice, true, 'Missing static-state warning');
  assert.ok(m.scrollWidth <= m.width, 'Horizontal overflow');
  assert.equal(m.visibleCards, 4, 'Hidden or clipped card');
}

async function main() {
  const destination = process.argv[2];
  if (!destination || process.argv.length !== 3) {
    throw new Error('Usage: node scripts/validate_catalog_visual.cjs NEW_DIRECTORY');
  }
  // Exclusive directory creation protects previous screenshots and evidence.
  fs.mkdirSync(destination);
  const result = { status: 'incomplete', checks: [], screenshots: [], networkAttempts: 0 };
  let browser;
  try {
    const generated = spawnSync(process.env.GENSIA_PYTHON || 'python3',
      ['-m', 'gensia.catalog_report'], {
        cwd: path.resolve(__dirname, '..'), encoding: 'utf8', timeout: 15000,
        maxBuffer: 1024 * 1024,
      });
    if (generated.error || generated.status !== 0) throw new Error('HTML generation failed');
    const { chromium } = require('playwright');
    result.playwright = require('playwright/package.json').version;
    browser = await chromium.launch({ headless: true });
    result.browser = browser.version();
    const context = await browser.newContext({ offline: true, serviceWorkers: 'block' });
    await context.route('**/*', route => {
      result.networkAttempts++;
      return route.abort();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.setContent(generated.stdout, { waitUntil: 'load' });
      const metrics = await page.evaluate(() => {
        const cards = [...document.querySelectorAll('article')];
        return {
          width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
          cards: cards.length,
          notice: document.querySelector('.notice')?.textContent.includes('não indica agentes ativos') === true,
          visibleCards: cards.filter(card => {
            const r = card.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.left >= 0 && r.right <= innerWidth;
          }).length,
        };
      });
      validateMetrics(metrics);
      result.checks.push(metrics);
      const filename = `catalog-${width}.png`;
      await page.screenshot({ path: path.join(destination, filename), fullPage: true });
      result.screenshots.push(filename);
    }
    assert.equal(result.networkAttempts, 0, 'Unexpected network request');
    result.status = 'passed';
  } catch (error) {
    result.status = 'failed';
    result.error = error.message;
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => {});
    fs.writeFileSync(path.join(destination, 'validation.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(result));
  }
}

module.exports = { validateMetrics };
if (require.main === module) main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
