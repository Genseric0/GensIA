(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const form = byId('connect-form'), input = byId('api-token');
  const connect = byId('connect'), refresh = byId('refresh'), clear = byId('disconnect');
  const data = byId('diagnostic-data'), status = byId('connection-status');
  let token = '', controller = null, generation = 0;
  const resources = [
    ['address_space_bytes', 'Espaço virtual', 'bytes'], ['cpu_seconds', 'Tempo de CPU', 's'],
    ['file_bytes', 'Tamanho por ficheiro', 'bytes'], ['core_bytes', 'Core dump', 'bytes'],
  ];
  function disconnect(message = 'Sessão limpa. Introduz o token para voltar a consultar.') {
    generation++; if (controller) controller.abort(); controller = null; token = '';
    input.value = ''; form.hidden = false; data.hidden = true; clear.hidden = true;
    refresh.hidden = true; refresh.disabled = true; connect.disabled = false;
    byId('limit-rows').replaceChildren(); byId('warning-list').replaceChildren();
    for (const id of ['version', 'runtime', 'read-mode', 'read-detail', 'quota-state']) byId(id).textContent = '—';
    status.textContent = message;
  }
  const safeText = value => typeof value === 'string' ? value.slice(0, 200) : 'Não informado';
  function amount(value, unit) {
    if (!Number.isSafeInteger(value) || value < 0) return 'Não confirmado';
    if (unit === 's') return `${value} s`;
    return value >= 1048576 ? `${(value / 1048576).toFixed(2)} MiB` : `${value} bytes`;
  }
  async function boundedJson(response) {
    if (!response.headers.get('content-type')?.toLowerCase().startsWith('application/json')) throw new Error('invalid');
    const reader = response.body.getReader(), chunks = []; let size = 0;
    try {
      while (true) {
        const {done, value} = await reader.read(); if (done) break;
        size += value.byteLength; if (size > 65536) throw new Error('large');
        chunks.push(value);
      }
    } catch (error) { await reader.cancel().catch(() => {}); throw error; }
    finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
  }
  function render(report) {
    const p = report?.document_protections, mode = p?.document_reads?.mode;
    const limits = p?.pdf_worker?.resource_limits;
    if (p?.schema_version !== 1 || p.commercial_approval !== false || p.os_sandbox !== false ||
        !['descriptor_relative', 'path_compatibility'].includes(mode) ||
        !['available_unverified', 'unsupported', 'unavailable'].includes(limits?.state)) throw new Error('invalid');
    byId('version').textContent = `GensIA ${safeText(p.gensia_version)}`;
    byId('runtime').textContent = `${safeText(p.platform)} · Python ${safeText(report.python)}`;
    byId('read-mode').textContent = mode === 'descriptor_relative' ? 'Por descritores' : 'Compatibilidade';
    byId('read-detail').textContent = mode === 'descriptor_relative' ? 'Via POSIX disponível. Execução não testada nesta consulta.' : 'Sem a proteção POSIX contra trocas concorrentes.';
    byId('quota-state').textContent = ({available_unverified: 'Disponíveis, não testadas', unsupported: 'Não suportadas', unavailable: 'Não confirmadas'})[limits.state];
    byId('limit-rows').replaceChildren();
    for (const [key, title, unit] of resources) {
      const row = document.createElement('tr');
      for (const text of [title, amount(limits.configured_caps?.[key], unit), amount(limits.planned_caps?.[key], unit)]) {
        const cell = document.createElement('td'); cell.textContent = text; row.appendChild(cell);
      }
      byId('limit-rows').appendChild(row);
    }
    byId('warning-list').replaceChildren();
    const warnings = Array.isArray(p.warnings) ? p.warnings.slice(0, 8) : [];
    for (const text of ['Não aprovado para uso comercial. Não é uma sandbox.', ...warnings]) {
      const item = document.createElement('li'); item.textContent = safeText(text); byId('warning-list').appendChild(item);
    }
    data.hidden = false;
  }
  async function load(isRefresh) {
    const candidate = isRefresh ? token : input.value.trim(); input.value = '';
    if (!/^[A-Za-z0-9]{32,256}$/.test(candidate)) { disconnect('Token inválido: usa 32–256 caracteres alfanuméricos.'); return; }
    if (controller) controller.abort();
    token = candidate; controller = new AbortController(); const request = controller;
    const current = ++generation; form.hidden = true; clear.hidden = false;
    refresh.hidden = false; refresh.disabled = true; connect.disabled = true;
    data.hidden = true; status.textContent = 'A consultar metadados locais…';
    const timer = setTimeout(() => request.abort(), 5000);
    try {
      const response = await fetch('/diagnostics', {method: 'GET', mode: 'same-origin', credentials: 'omit',
        cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
        headers: {Authorization: `Bearer ${candidate}`}, signal: request.signal});
      if (response.status === 401) throw new Error('unauthorized');
      if (!response.ok) throw new Error('unavailable');
      const report = await boundedJson(response);
      if (current !== generation) return;
      render(report); status.textContent = 'Metadados recebidos. Capacidades não equivalem a aplicação validada.';
    } catch (error) {
      if (current === generation) disconnect(error.message === 'unauthorized' ? 'Token recusado. Introduz novamente o token local.' : 'Consulta falhou ou excedeu o prazo. A sessão foi limpa; tenta novamente.');
    } finally {
      clearTimeout(timer); if (current === generation) { controller = null; refresh.disabled = false; connect.disabled = false; }
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); return load(false); });
  refresh.addEventListener('click', () => load(true));
  clear.addEventListener('click', () => disconnect());
  window.addEventListener('pagehide', () => disconnect());
  if (window.location.protocol !== 'http:' || window.location.hostname !== '127.0.0.1' || window.location.search || window.location.hash) {
    status.textContent = 'Abre o painel pela API em http://127.0.0.1:PORTA/panel, sem query ou fragmento.';
    return;
  }
  input.disabled = false; connect.disabled = false;
})();
