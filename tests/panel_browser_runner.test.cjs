const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {parseReady, requestAllowed, validateMetrics, evidenceComplete, childEnvironment,
  startServer, waitHealthy, stopServer, run} = require('../scripts/validate_panel_browser.cjs');

test('server readiness accepts only an ephemeral local port and version metadata', () => {
  assert.deepEqual(parseReady('{"event":"listening","port":12345,"python":"3.12.14"}'), {port: 12345, python: '3.12.14'});
  for (const value of ['{}', 'SECRET', 'x'.repeat(4097),
    '{"event":"listening","port":80,"python":"3.12.14"}',
    '{"event":"listening","port":65536,"python":"3.12.14"}',
    '{"event":"listening","port":12345,"python":"PRIVATE"}']) assert.throws(() => parseReady(value));
});

test('browser request policy rejects external requests, mutations, query tokens and header leakage', () => {
  const origin = 'http://127.0.0.1:12345';
  for (const pathname of ['/panel', '/panel.js', '/panel.css', '/diagnostics']) assert.equal(requestAllowed(origin + pathname, 'GET', undefined, origin), true);
  assert.equal(requestAllowed(origin + '/diagnostics', 'GET', 'Bearer test', origin), true);
  for (const [url, method, auth] of [
    ['https://evil.example/panel', 'GET'], [origin + '/panel?token=SECRET', 'GET'],
    [origin + '/panel#SECRET', 'GET'], [origin + '/diagnostics', 'POST'],
    [origin + '/panel.js', 'GET', 'Bearer SECRET'], ['http://localhost:12345/panel', 'GET'],
    ['http://127.0.0.1:12346/panel', 'GET'], [origin + '/memory', 'GET'],
  ]) assert.equal(requestAllowed(url, method, auth, origin), false);
});

test('metrics do not approve overflow, missing cards, rows or unloaded CSS', () => {
  const good = {width: 390, scrollWidth: 390, cards: 3, visibleCards: 3, rows: 4, cssLoaded: true};
  validateMetrics(good);
  for (const change of [{width: 400}, {scrollWidth: 391}, {cards: 2}, {visibleCards: 1}, {rows: 0}, {cssLoaded: false}]) assert.throws(() => validateMetrics({...good, ...change}));
});

test('partial evidence never becomes passed evidence', () => {
  const data = {checks: [], screenshots: [], metrics: [], external_attempts: 0, page_errors: 0, csp_violations: 0};
  assert.equal(evidenceComplete(data), false);
  data.checks = ['locked', 'keyboard_auth', 'manual_refresh', 'storage_empty', 'invalid_token',
    'session_clear', 'reload_locked', 'csp_clean', 'same_origin_only'];
  data.screenshots = ['panel-locked-1440.png', 'panel-auth-1440.png', 'panel-auth-390.png', 'panel-auth-320.png'];
  data.metrics = [1440, 390, 320].map(width => ({width, scrollWidth: width, cards: 3, visibleCards: 3, rows: 4, cssLoaded: true}));
  assert.equal(evidenceComplete(data), true);
  assert.equal(evidenceComplete({...data, external_attempts: 1}), false);
  assert.equal(evidenceComplete({...data, csp_violations: 1}), false);
  assert.equal(evidenceComplete({...data, page_errors: 1}), false);
  assert.equal(evidenceComplete({...data, screenshots: ['a.png', 'b.png', 'c.png', 'd.png']}), false);
  assert.equal(evidenceComplete({...data, metrics: [data.metrics[0], data.metrics[0], data.metrics[0]]}), false);
});

test('child environment does not inherit existing credentials or Python path overrides', () => {
  const names = ['GENSIA_API_TOKEN', 'VIRUSTOTAL_API_KEY', 'PYTHONPATH', 'HTTP_PROXY'];
  const old = names.map(name => process.env[name]);
  try {
    names.forEach(name => { process.env[name] = 'PRIVATE'; });
    const env = childEnvironment('ephemeral');
    assert.equal(env.GENSIA_API_TOKEN, 'ephemeral');
    for (const name of names.slice(1)) assert.equal(env[name], undefined);
    assert.equal(env.PYTHONDONTWRITEBYTECODE, '1');
  } finally {
    names.forEach((name, index) => { if (old[index] === undefined) delete process.env[name]; else process.env[name] = old[index]; });
  }
});

test('missing browser produces sanitized blocked evidence with no screenshots', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'gensia-panel-runner-'));
  t.after(() => fs.rmSync(root, {recursive: true}));
  const destination = path.join(root, 'new-evidence');
  const report = await run(destination, {playwright: {chromium: {launch: async () => { throw new Error('PRIVATE TOKEN PATH'); }}}});
  assert.equal(report.status, 'blocked'); assert.equal(report.failure_stage, 'browser_launch');
  assert.deepEqual(report.screenshots, []); assert.equal(report.checks.length, 0);
  assert.equal(report.cleanup.server_stopped, true);
  const saved = fs.readFileSync(path.join(destination, 'validation.json'), 'utf8');
  assert.doesNotMatch(saved, /PRIVATE|TOKEN|PATH/);
});

test('existing evidence directory is preserved without launching a browser', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'gensia-panel-preserve-'));
  t.after(() => fs.rmSync(root, {recursive: true}));
  const file = path.join(root, 'keep.txt'); fs.writeFileSync(file, 'original');
  let launches = 0;
  await assert.rejects(run(root, {playwright: {chromium: {launch: async () => { launches++; }}}}));
  assert.equal(fs.readFileSync(file, 'utf8'), 'original'); assert.equal(launches, 0);
});

test('real Node helper lifecycle uses its own reserved API and stops the child',
  {skip: !process.env.GENSIA_PYTHON, timeout: 15000}, async () => {
    const token = require('node:crypto').randomBytes(32).toString('hex'); let child;
    try {
      const ready = await startServer(process.env.GENSIA_PYTHON, token, value => { child = value; });
      await waitHealthy(ready.port, token, child);
      assert.equal(await stopServer(child), true);
      assert.ok(child.exitCode !== null || child.signalCode !== null);
    } finally { await stopServer(child); }
  });
