// Optional development E2E. Never downloads browsers, reuses accounts, or targets an existing service.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const {spawn} = require('node:child_process');
const ROOT = path.resolve(__dirname, '..');
const REQUIRED = ['locked', 'keyboard_auth', 'manual_refresh', 'storage_empty', 'invalid_token',
  'session_clear', 'reload_locked', 'csp_clean', 'same_origin_only'];
const REQUIRED_IMAGES = ['panel-locked-1440.png', 'panel-auth-1440.png', 'panel-auth-390.png', 'panel-auth-320.png'];

function check(value) { if (!value) throw new Error('validation_failed'); }
function parseReady(line) {
  check(typeof line === 'string' && line.length <= 4096);
  const data = JSON.parse(line);
  check(data.event === 'listening' && Number.isInteger(data.port) && data.port >= 1024 && data.port <= 65535);
  check(typeof data.python === 'string' && /^\d+\.\d+\.\d+$/.test(data.python));
  return {port: data.port, python: data.python};
}
function requestAllowed(url, method, authorization, origin) {
  try {
    const parsed = new URL(url);
    if (url === 'data:,') return method === 'GET' && !authorization;
    return method === 'GET' && parsed.origin === origin && !parsed.search && !parsed.hash &&
      ['/panel', '/panel.js', '/panel.css', '/diagnostics', '/favicon.ico'].includes(parsed.pathname) &&
      (!authorization || parsed.pathname === '/diagnostics');
  } catch { return false; }
}
function validateMetrics(m) {
  check([1440, 390, 320].includes(m.width) && Number.isInteger(m.scrollWidth) && m.scrollWidth > 0 && m.scrollWidth <= m.width);
  check(m.cards === 3 && m.visibleCards === 3 && m.rows === 4 && m.cssLoaded === true);
}
function evidenceComplete(report) {
  return REQUIRED.every(name => report.checks.includes(name)) && report.screenshots.length === 4 &&
    REQUIRED_IMAGES.every(name => report.screenshots.includes(name)) && report.metrics.length === 3 &&
    new Set(report.metrics.map(m => m.width)).size === 3 &&
    report.metrics.every(m => { try { validateMetrics(m); return true; } catch { return false; } }) &&
    report.external_attempts === 0 && report.page_errors === 0 && report.csp_violations === 0;
}
function childEnvironment(token) {
  const environment = {GENSIA_API_TOKEN: token, PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1'};
  for (const name of ['PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR']) {
    if (process.env[name]) environment[name] = process.env[name];
  }
  return environment;
}
async function startServer(python, token, onSpawn) {
  const child = spawn(python, ['-I', '-B', path.join(ROOT, 'scripts/panel_test_server.py')], {
    cwd: ROOT, env: childEnvironment(token), shell: false, stdio: ['ignore', 'pipe', 'ignore'],
  });
  onSpawn(child);
  return new Promise((resolve, reject) => {
    let buffer = '';
    const timer = setTimeout(() => finish(false), 5000);
    const onError = () => finish(false);
    const onData = chunk => {
      buffer += chunk.toString('utf8');
      if (buffer.length > 4096) return finish(false);
      if (buffer.includes('\n')) {
        try { finish(true, parseReady(buffer.split('\n')[0])); } catch { finish(false); }
      }
    };
    function finish(ok, ready) {
      clearTimeout(timer); child.off('error', onError); child.off('exit', onError);
      child.stdout.off('data', onData); child.stdout.resume();
      if (ok) resolve(ready); else reject(new Error('server_start_failed'));
    }
    child.once('error', onError); child.once('exit', onError); child.stdout.on('data', onData);
  });
}
function health(port, token) {
  return new Promise(resolve => {
    const request = http.get({hostname: '127.0.0.1', port, path: '/health',
      headers: {Authorization: `Bearer ${token}`}, timeout: 500}, response => {
      response.resume(); resolve(response.statusCode === 200);
    });
    request.on('timeout', () => request.destroy()); request.on('error', () => resolve(false));
  });
}
async function waitHealthy(port, token, child) {
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    if (child && (child.exitCode !== null || child.signalCode !== null)) throw new Error('server_exited');
    if (await health(port, token)) {
      if (child && (child.exitCode !== null || child.signalCode !== null)) throw new Error('server_exited');
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 30));
  }
  throw new Error('server_not_ready');
}
function waitExit(child, milliseconds) {
  if (!child || !child.pid || child.exitCode !== null || child.signalCode !== null) return Promise.resolve(true);
  return new Promise(resolve => {
    const done = value => { clearTimeout(timer); child.off('exit', onExit); resolve(value); };
    const onExit = () => done(true);
    const timer = setTimeout(() => done(false), milliseconds); child.once('exit', onExit);
  });
}
async function stopServer(child) {
  if (await waitExit(child, 0)) return true;
  child.kill('SIGTERM'); if (await waitExit(child, 2500)) return true;
  child.kill('SIGKILL'); return waitExit(child, 1000);
}

async function run(destination, options = {}) {
  // Exclusive creation preserves all existing evidence, including symlink targets.
  fs.mkdirSync(destination, {mode: 0o700});
  const report = {schema_version: 1, status: 'incomplete', checks: [], metrics: [], screenshots: [],
    external_attempts: 0, page_errors: 0, csp_violations: 0, token_recorded: false, browser_flow_started: false,
    cleanup: {browser_closed: false, server_stopped: false}};
  let stage = 'playwright_load', browser, child;
  const token = crypto.randomBytes(32).toString('hex');
  try {
    const playwright = options.playwright || require('playwright');
    try { report.playwright = require('playwright/package.json').version; } catch { report.playwright = 'not_resolved'; }
    stage = 'browser_launch';
    if (typeof playwright.chromium.executablePath === 'function') {
      report.browser_executable_present = fs.existsSync(playwright.chromium.executablePath());
      check(report.browser_executable_present);
    }
    browser = await playwright.chromium.launch({headless: true, timeout: 10000});
    report.browser = browser.version();
    stage = 'server_start';
    const ready = await startServer(process.env.GENSIA_PYTHON || 'python3', token, value => { child = value; });
    report.python = ready.python; await waitHealthy(ready.port, token, child);
    const origin = `http://127.0.0.1:${ready.port}`;
    stage = 'panel_flow';
    report.browser_flow_started = true;
    const context = await browser.newContext({serviceWorkers: 'block', acceptDownloads: false});
    let diagnosticRequests = 0;
    await context.route('**/*', async route => {
      const request = route.request(); const auth = (await request.allHeaders()).authorization;
      if (!requestAllowed(request.url(), request.method(), auth, origin)) {
        report.external_attempts++; return route.abort();
      }
      if (new URL(request.url()).pathname === '/diagnostics') diagnosticRequests++;
      return route.continue();
    });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    page.on('pageerror', () => { report.page_errors++; });
    await page.addInitScript(() => {
      window.__gensiaCspCount = 0;
      document.addEventListener('securitypolicyviolation', () => { window.__gensiaCspCount++; });
    });
    await page.setViewportSize({width: 1440, height: 1000});
    await page.goto(origin + '/panel', {waitUntil: 'networkidle'});
    await page.waitForFunction(() => !document.getElementById('api-token').disabled);
    check(!(await page.locator('#diagnostic-data').isVisible()) && diagnosticRequests === 0);
    report.checks.push('locked');
    async function capture(filename) {
      check(await page.locator('#api-token').inputValue() === '');
      check(!await page.locator('body').textContent().then(text => text.includes(token)));
      check(page.url() === origin + '/panel');
      const image = await page.screenshot({fullPage: true}); check(image.length <= 5 * 1024 * 1024);
      fs.writeFileSync(path.join(destination, filename), image, {flag: 'wx', mode: 0o600});
      report.screenshots.push(filename);
    }
    stage = 'capture'; await capture('panel-locked-1440.png'); stage = 'panel_flow';
    await page.locator('#api-token').fill(token); await page.locator('#api-token').press('Enter');
    await page.locator('#diagnostic-data').waitFor({state: 'visible'});
    check(await page.locator('#api-token').inputValue() === ''); report.checks.push('keyboard_auth');
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      const metrics = await page.evaluate(() => {
        const cards = [...document.querySelectorAll('.cards article')];
        return {width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
          cards: cards.length, rows: document.querySelectorAll('#limit-rows tr').length,
          cssLoaded: getComputedStyle(document.body).backgroundColor === 'rgb(12, 17, 25)',
          visibleCards: cards.filter(card => { const r = card.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth; }).length};
      });
      validateMetrics(metrics); report.metrics.push(metrics);
      stage = 'capture'; await capture(`panel-auth-${width}.png`); stage = 'panel_flow';
    }
    const count = diagnosticRequests;
    const refreshed = page.waitForResponse(response => response.url() === origin + '/diagnostics' && response.status() === 200);
    await page.locator('#refresh').press('Enter'); await refreshed;
    check(diagnosticRequests === count + 1); report.checks.push('manual_refresh');
    const storage = await page.evaluate(() => ({local: localStorage.length, session: sessionStorage.length}));
    check(storage.local === 0 && storage.session === 0 && (await context.cookies()).length === 0);
    report.checks.push('storage_empty');
    await page.locator('#disconnect').click();
    check(!await page.locator('#diagnostic-data').isVisible());
    check(await page.locator('#limit-rows tr').count() === 0); report.checks.push('session_clear');
    const wrong = (token[0] === 'a' ? 'b' : 'a') + token.slice(1);
    await page.locator('#api-token').fill(wrong); await page.locator('#api-token').press('Enter');
    await page.waitForFunction(() => document.getElementById('connection-status').textContent.includes('Token recusado'));
    check(!await page.locator('#diagnostic-data').isVisible()); report.checks.push('invalid_token');
    report.csp_violations += await page.evaluate(() => window.__gensiaCspCount);
    const beforeReload = diagnosticRequests;
    await page.reload({waitUntil: 'networkidle'});
    await page.waitForFunction(() => !document.getElementById('api-token').disabled);
    check(!await page.locator('#diagnostic-data').isVisible() && diagnosticRequests === beforeReload);
    report.checks.push('reload_locked');
    report.csp_violations += await page.evaluate(() => window.__gensiaCspCount);
    check(report.csp_violations === 0 && report.page_errors === 0); report.checks.push('csp_clean');
    check(report.external_attempts === 0); report.checks.push('same_origin_only');
    check(evidenceComplete(report)); report.status = 'passed';
  } catch {
    report.status = ['playwright_load', 'browser_launch', 'server_start'].includes(stage) ? 'blocked' : 'failed';
    report.failure_stage = stage; // Static stage only: never serialize errors, tokens, URLs or headers.
    if (stage === 'browser_launch' && report.browser_executable_present === false) report.failure_reason = 'browser_executable_missing';
  } finally {
    try { if (browser) await browser.close(); report.cleanup.browser_closed = true; } catch {}
    report.cleanup.server_stopped = await stopServer(child);
    if (!report.cleanup.browser_closed || !report.cleanup.server_stopped) report.status = 'failed';
    if (report.status === 'passed' && !evidenceComplete(report)) report.status = 'failed';
    fs.writeFileSync(path.join(destination, 'validation.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx', mode: 0o600});
  }
  return report;
}

module.exports = {parseReady, requestAllowed, validateMetrics, evidenceComplete, childEnvironment,
  startServer, waitHealthy, stopServer, run};
if (require.main === module) {
  if (process.argv.length !== 3) { console.error('Usage: node scripts/validate_panel_browser.cjs NEW_DIRECTORY'); process.exitCode = 2; }
  else run(path.resolve(process.argv[2])).then(report => {
    console.log(JSON.stringify(report)); process.exitCode = report.status === 'passed' ? 0 : report.status === 'blocked' ? 2 : 1;
  }).catch(() => { console.error('Evidence directory unavailable; no existing files replaced.'); process.exitCode = 1; });
}
