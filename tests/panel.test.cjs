// DOM control-flow tests, not a browser/layout/CSP implementation.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../gensia/web/panel.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../gensia/web/panel.html'), 'utf8');
const TOKEN = 'testtoken'.repeat(8);
const fixture = () => ({python: '3.12.14', document_protections: {
  schema_version: 1, gensia_version: '0.32.0', platform: 'linux', os_sandbox: false,
  commercial_approval: false, document_reads: {mode: 'descriptor_relative'},
  pdf_worker: {resource_limits: {state: 'available_unverified',
    configured_caps: {address_space_bytes: 536870912, cpu_seconds: 30, file_bytes: 2097152, core_bytes: 0},
    planned_caps: {address_space_bytes: 536870912, cpu_seconds: 30, file_bytes: 2097152, core_bytes: 0}}},
  warnings: ['Não é sandbox.'],
}});
const jsonResponse = value => new Response(JSON.stringify(value), {headers: {'content-type': 'application/json'}});

function setup(fetcher = async () => jsonResponse(fixture()), location = {}) {
  class Element {
    constructor() { this.value = ''; this.textContent = ''; this.hidden = false; this.disabled = false; this.handlers = {}; this.children = []; }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    replaceChildren(...children) { this.children = children; }
    appendChild(child) { this.children.push(child); }
    set innerHTML(value) { throw new Error('HTML injection sink forbidden'); }
  }
  const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element()]));
  elements['diagnostic-data'].hidden = true;
  for (const name of ['refresh', 'disconnect']) elements[name].hidden = true;
  elements.refresh.disabled = true;
  elements['api-token'].disabled = true; elements.connect.disabled = true;
  const document = {getElementById(id) { assert.ok(elements[id], `Unknown DOM id ${id}`); return elements[id]; },
    createElement() { return new Element(); }};
  const events = {}, calls = [], timers = [];
  const window = {location: {protocol: 'http:', hostname: '127.0.0.1', search: '', hash: '', ...location},
    addEventListener(name, handler) { events[name] = handler; }};
  for (const name of ['localStorage', 'sessionStorage']) Object.defineProperty(window, name, {get() { throw new Error('No token persistence'); }});
  const context = {document, window, AbortController, TextDecoder,
    fetch: async (...args) => { calls.push(args); return fetcher(...args); },
    setTimeout(cb, ms) { const timer = {cb, ms}; timers.push(timer); return timer; },
    clearTimeout(timer) { timer.cleared = true; }};
  for (const name of ['localStorage', 'sessionStorage']) Object.defineProperty(context, name, {get() { throw new Error('No token persistence'); }});
  vm.runInNewContext(source, context, {timeout: 1000});
  return {elements, events, calls, timers,
    submit(value = TOKEN) { elements['api-token'].value = value; return elements['connect-form'].handlers.submit({preventDefault() {}}); }};
}

test('initial shell does not fetch or display diagnostic data', () => {
  const ui = setup(); assert.equal(ui.calls.length, 0);
  assert.equal(ui.elements['diagnostic-data'].hidden, true);
  assert.equal(ui.elements['api-token'].disabled, false);
});

test('token is only sent in header; refresh is manual and clear prevents reuse', async () => {
  const ui = setup(); await ui.submit();
  assert.equal(ui.calls.length, 1); const [url, options] = ui.calls[0];
  assert.equal(url, '/diagnostics'); assert.equal(options.method, 'GET');
  assert.equal(options.headers.Authorization, `Bearer ${TOKEN}`);
  for (const [key, value] of Object.entries({mode: 'same-origin', credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer'})) assert.equal(options[key], value);
  assert.equal(ui.elements['api-token'].value, '');
  assert.equal(ui.elements['diagnostic-data'].hidden, false);
  assert.equal(ui.elements['quota-state'].textContent, 'Disponíveis, não testadas');
  assert.equal(ui.elements['limit-rows'].children.length, 4);
  await ui.elements.refresh.handlers.click(); assert.equal(ui.calls.length, 2);
  ui.elements.disconnect.handlers.click(); await ui.elements.refresh.handlers.click();
  assert.equal(ui.calls.length, 2); assert.equal(ui.elements['diagnostic-data'].hidden, true);
  assert.equal(ui.elements.version.textContent, '—');
  assert.equal(ui.elements['limit-rows'].children.length, 0);
});

test('invalid tokens never cause a request', async () => {
  const ui = setup(); await ui.submit('short');
  assert.equal(ui.calls.length, 0); assert.match(ui.elements['connection-status'].textContent, /Token inválido/);
});

test('401 clears session without displaying or reading remote error body', async () => {
  const ui = setup(async () => new Response(`PRIVATE ${TOKEN}`, {status: 401}));
  await ui.submit(); assert.match(ui.elements['connection-status'].textContent, /Token recusado/);
  assert.equal(ui.elements['connect-form'].hidden, false);
  assert.equal(ui.elements['diagnostic-data'].hidden, true);
  assert.doesNotMatch(ui.elements['connection-status'].textContent, /PRIVATE|testtoken/);
});

test('oversized JSON is refused and remote text is never reflected as an error', async () => {
  const ui = setup(async () => new Response('PRIVATE'.repeat(12000), {headers: {'content-type': 'application/json'}}));
  await ui.submit(); assert.equal(ui.elements['diagnostic-data'].hidden, true);
  assert.match(ui.elements['connection-status'].textContent, /Consulta falhou/);
  assert.doesNotMatch(ui.elements['connection-status'].textContent, /PRIVATE/);
});

test('invalid schema cannot be rendered as validated protection', async () => {
  const value = fixture(); value.document_protections.commercial_approval = true;
  const ui = setup(async () => jsonResponse(value)); await ui.submit();
  assert.equal(ui.elements['diagnostic-data'].hidden, true);
});

test('untrusted strings remain text, not HTML', async () => {
  const value = fixture(); value.document_protections.warnings = ['<img src=x onerror=alert(1)>'];
  const ui = setup(async () => jsonResponse(value)); await ui.submit();
  assert.equal(ui.elements['warning-list'].children[1].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(ui.elements['diagnostic-data'].hidden, false);
});

test('late response after clear cannot repopulate the panel', async () => {
  let resolve;
  const ui = setup(() => new Promise(done => { resolve = done; }));
  const pending = ui.submit(); ui.elements.disconnect.handlers.click();
  assert.equal(ui.calls[0][1].signal.aborted, true);
  resolve(jsonResponse(fixture())); await pending;
  assert.equal(ui.elements['diagnostic-data'].hidden, true);
  assert.equal(ui.elements['limit-rows'].children.length, 0);
});

test('five-second abort clears an unresponsive request', async () => {
  const ui = setup((url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('PRIVATE timeout')));
  }));
  const pending = ui.submit(); assert.equal(ui.timers[0].ms, 5000); ui.timers[0].cb(); await pending;
  assert.equal(ui.elements['diagnostic-data'].hidden, true);
  assert.doesNotMatch(ui.elements['connection-status'].textContent, /PRIVATE/);
});

test('file pages, alternate hosts and URL credentials are not accepted', () => {
  for (const location of [{protocol: 'file:'}, {hostname: 'localhost'}, {search: '?token=PRIVATE'}, {hash: '#PRIVATE'}]) {
    const ui = setup(undefined, location);
    assert.equal(ui.elements['api-token'].disabled, true); assert.equal(ui.calls.length, 0);
  }
});
