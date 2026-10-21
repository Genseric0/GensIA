(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const form = el('chat-form'), prompt = el('prompt'), send = el('send'), cancel = el('cancel');
  const input = el('api-token'), connect = el('connect'), connectForm = el('connect-form');
  const messageList = el('messages'), welcome = el('welcome'), status = el('request-status');
  const connectionStatus = el('connection-status'), badge = el('model-badge');
  let token = '', ready = false, busy = false, request = null, generation = 0, history = [];
  let apiVerified = false, firstReply = false, guideReason = 'token';
  let deadline = 0, monotonicDeadline = 0, idleTimer = null, previousWall = Date.now();
  const IDLE = 300000;
  const GUIDE = {
    token: 'Começa pelo token apresentado no terminal. O token muda ao reiniciar com --ephemeral-token.',
    checking: 'A consultar metadados. Esta verificação não envia a conversa nem testa inferência.',
    configure: 'API verificada, mas a conversa está desativada. Reinicia a GensIA com --chat-model e um modelo local já instalado.',
    metadata: 'Metadados locais confirmados. Falta testar uma resposta: escreve uma pergunta sem dados sensíveis.',
    reply: 'Primeira resposta recebida nesta conversa. Isto não certifica qualidade, segurança, hardware ou desempenho.',
    connection_failed: 'Confirma que o Ollama está a correr no mesmo computador. Depois volta a ligar com o token da GensIA.',
    model_not_found: 'Executa ollama list no computador da GensIA e usa o nome exato de um modelo local já instalado ao reiniciar.',
    cloud_model_blocked: 'O modelo foi recusado por usar processamento remoto. Escolhe um modelo local e reinicia a GensIA.',
    locality_unconfirmed: 'A localidade do modelo não foi confirmada. Revê o daemon e o modelo; a conversa mantém-se bloqueada.',
    model_busy: 'O servidor ainda está ocupado. Aguarda e verifica novamente de forma manual.',
    model_required: 'Reinicia a GensIA com --chat-model e o nome exato de um modelo local já instalado.',
    failed: 'Verificação inconclusiva. Confirma a execução da GensIA e do Ollama antes de voltar a ligar.',
    browser: 'Abre a interface em http://127.0.0.1:PORTA/app no computador da GensIA, sem parâmetros no endereço.'
  };
  const ERROR = {chat_not_configured: 'Liga um modelo ao iniciar a GensIA para conversar.',
    connection_failed: 'Não foi possível contactar o Ollama. Confirma que está ativo.',
    model_not_found: 'Modelo não encontrado. Confirma o nome e a instalação no Ollama.',
    cloud_model_blocked: 'Este modelo usa processamento remoto. Escolhe um modelo local.',
    locality_unconfirmed: 'Não foi possível confirmar que o modelo é local.',
    model_busy: 'O modelo ainda está a processar um pedido. Aguarda antes de tentar novamente.',
    model_required: 'Escolhe um modelo local ao iniciar a GensIA.',
    invalid_response: 'O modelo devolveu uma resposta inválida.',
    invalid_model_response: 'O modelo devolveu uma resposta inválida ou demasiado extensa.',
    unsafe_text: 'O modelo devolveu uma resposta com caracteres não suportados.',
    response_too_large: 'A resposta excedeu o limite. Tenta uma pergunta mais curta.',
    context_too_large: 'A conversa excedeu o contexto permitido. Inicia uma nova conversa.'};
  const local = window.location.protocol === 'http:' && window.location.hostname === '127.0.0.1'
    && !window.location.search && !window.location.hash
    && !window.location.username && !window.location.password;
  function guide() {
    el('setup-progress').textContent = `${Number(apiVerified) + Number(ready) + Number(firstReply)} de 3 passos`;
    el('setup-api').textContent = apiVerified ? 'Ligação verificada' : 'Por verificar';
    el('setup-model').textContent = ready ? 'Metadados locais confirmados' : 'Por verificar';
    el('setup-reply').textContent = firstReply ? 'Resposta recebida nesta conversa' : 'Por testar';
    el('setup-hint').textContent = GUIDE[guideReason] || GUIDE.failed;
  }
  function controls() {
    prompt.disabled = !ready || busy; send.disabled = !ready || busy || !prompt.value.trim();
    cancel.hidden = !busy; send.hidden = busy;
    el('check-model').disabled = busy || !token;
    el('char-count').textContent = `${prompt.value.length} / 4000`;
    guide();
  }
  function clearConversation(message = '') {
    generation++; if (request) request.abort(); request = null; busy = false; history = [];
    messageList.replaceChildren(); messageList.hidden = true; welcome.hidden = false;
    prompt.value = ''; status.textContent = message;
    firstReply = false; if (ready) guideReason = 'metadata'; controls();
  }
  function disconnect(message = 'Sessão terminada. Introduz novamente o token local.', reason = 'token') {
    token = ''; ready = false; clearTimeout(idleTimer); deadline = 0; monotonicDeadline = 0;
    apiVerified = false; firstReply = false; guideReason = reason;
    clearConversation(); input.value = ''; connectForm.hidden = false; connect.disabled = !local;
    el('clear-session').hidden = true; el('check-model').hidden = true;
    badge.classList.remove('connected'); badge.lastChild.textContent = 'Modelo por ligar';
    connectionStatus.textContent = message;
    if (reason !== 'token') el('setup-guide').open = true;
  }
  function expires() {
    const now = Date.now(), rolledBack = now < previousWall; previousWall = now;
    if (!token || (!rolledBack && now < deadline && performance.now() < monotonicDeadline)) return false;
    disconnect('Sessão expirada. A conversa foi limpa; o token da API continua válido até terminar o servidor.');
    return true;
  }
  function renew() {
    clearTimeout(idleTimer); previousWall = Date.now(); deadline = previousWall + IDLE;
    monotonicDeadline = performance.now() + IDLE;
    function check() {
      if (!token || expires()) return;
      idleTimer = setTimeout(check, Math.max(1, Math.min(deadline - Date.now(), monotonicDeadline - performance.now())));
    }
    idleTimer = setTimeout(check, IDLE);
  }
  async function json(response) {
    if (!response.headers.get('content-type')?.toLowerCase().startsWith('application/json')) throw new Error('invalid');
    const reader = response.body.getReader(), chunks = []; let size = 0;
    try {
      while (true) {
        const item = await reader.read(); if (item.done) break;
        size += item.value.byteLength; if (size > 65536) throw new Error('invalid');
        chunks.push(item.value);
      }
    } catch (error) { await reader.cancel().catch(() => {}); throw error; }
    finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
  }
  function validText(value, max) {
    return typeof value === 'string' && value.trim() && value.length <= max
      && !/[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/u.test(value)
      && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value);
  }
  async function modelCheck(candidate) {
    if (!local || busy) return;
    if (token && expires()) return;
    input.value = '';
    if (!/^[A-Za-z0-9]{32,256}$/.test(candidate)) { disconnect('Token inválido. Usa o token completo do terminal.'); return; }
    token = candidate; connect.disabled = true; ready = false;
    apiVerified = false; firstReply = false; guideReason = 'checking'; controls(); renew();
    connectionStatus.textContent = 'A verificar o modelo local…';
    if (request) request.abort(); request = new AbortController(); const currentRequest = request;
    const current = ++generation, timer = setTimeout(() => currentRequest.abort(), 10000);
    try {
      const response = await fetch('/model', {method: 'GET', mode: 'same-origin', credentials: 'omit',
        cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
        headers: {Authorization: `Bearer ${candidate}`}, signal: currentRequest.signal});
      if (current !== generation || expires()) return;
      if (response.status === 401) { disconnect('Token recusado. Confirma o token da execução atual.'); return; }
      const data = await json(response);
      if (current !== generation || expires()) return;
      if (!response.ok) {
        const error = new Error(ERROR[data?.error] || 'Não foi possível verificar o modelo local.');
        error.guideCode = Object.hasOwn(ERROR, data?.error) && Object.hasOwn(GUIDE, data?.error) ? data.error : 'failed'; throw error;
      }
      if (data?.inference_tested !== false || typeof data.configured !== 'boolean' || typeof data.available !== 'boolean') throw new Error('Resposta de verificação inválida.');
      ready = data.configured === true && data.available === true && data.locality === 'confirmed_local';
      apiVerified = true; guideReason = ready ? 'metadata' : 'configure';
      el('setup-guide').open = !ready;
      connectForm.hidden = true; el('clear-session').hidden = false; el('check-model').hidden = false;
      badge.classList.toggle('connected', ready); badge.lastChild.textContent = ready ? 'Modelo local ligado' : 'Modelo por configurar';
      connectionStatus.textContent = ready ? 'Ligado. As tuas mensagens serão enviadas ao modelo local configurado.' : 'API ligada. Inicia a GensIA com um modelo Ollama local instalado para conversar.';
      if (ready) prompt.focus();
    } catch (error) {
      if (current === generation && !expires()) disconnect(ERROR[error.message] || (Object.values(ERROR).includes(error.message) ? error.message : 'A verificação falhou ou excedeu o prazo. Tenta novamente.'), error.guideCode || 'failed');
    } finally {
      clearTimeout(timer); if (current === generation) { request = null; connect.disabled = false; controls(); }
    }
  }
  function addMessage(role, text) {
    const article = document.createElement('article'); article.className = `message ${role}`;
    const icon = document.createElement('span'); icon.className = 'message-icon'; icon.setAttribute('aria-hidden', 'true'); icon.textContent = role === 'user' ? 'TU' : '✧';
    const content = document.createElement('div'); content.className = 'message-content';
    const title = document.createElement('h2'); title.textContent = role === 'user' ? 'Tu' : 'GensIA';
    const paragraph = document.createElement('p'); paragraph.textContent = text;
    content.appendChild(title); content.appendChild(paragraph); article.appendChild(icon); article.appendChild(content);
    messageList.appendChild(article); messageList.hidden = false; welcome.hidden = true;
    while (messageList.children.length > 40) messageList.firstElementChild.remove();
  }
  function contextFor(text) {
    let messages = history.slice(-8).map(item => ({...item})); messages.push({role: 'user', content: text});
    while (messages.length > 1 && (messages.reduce((n, item) => n + item.content.length, 0) > 12000
      || new TextEncoder().encode(JSON.stringify({messages})).byteLength > 32768)) messages.splice(0, 2);
    return messages;
  }
  async function submit() {
    if (!local || !ready || busy || expires()) return;
    const text = prompt.value.trim(); if (!validText(text, 4000)) { status.textContent = 'Escreve uma mensagem válida, até 4000 caracteres.'; return; }
    const messages = contextFor(text), current = ++generation; renew();
    busy = true; prompt.value = ''; controls(); status.textContent = 'A GensIA está a pensar…'; addMessage('user', text);
    request = new AbortController(); const currentRequest = request;
    const timer = setTimeout(() => currentRequest.abort(), 100000);
    try {
      const response = await fetch('/chat', {method: 'POST', mode: 'same-origin', credentials: 'omit',
        cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
        headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({messages}), signal: currentRequest.signal});
      if (current !== generation || expires()) return;
      if (response.status === 401) { disconnect('Token recusado. A sessão foi limpa.'); return; }
      const data = await json(response);
      if (current !== generation || expires()) return;
      if (!response.ok) { status.textContent = ERROR[data?.error] || 'O pedido falhou. Não foi repetido automaticamente.'; return; }
      if (!validText(data?.reply, 8000) || data.actions_executed !== false || data.cloud_fallback !== false) throw new Error('invalid');
      addMessage('assistant', data.reply); history = [...messages, {role: 'assistant', content: data.reply}].slice(-8);
      firstReply = true; guideReason = 'reply';
      status.textContent = 'Resposta recebida. Apenas os últimos pares que couberem no limite serão usados como contexto.';
    } catch {
      if (current === generation && !expires()) status.textContent = 'A espera terminou ou a ligação falhou. O servidor pode continuar a processar. Não houve repetição automática.';
    } finally {
      clearTimeout(timer); if (current === generation) { request = null; busy = false; controls(); prompt.focus(); }
    }
  }
  connectForm.addEventListener('submit', event => { event.preventDefault(); return modelCheck(input.value.trim()); });
  el('check-model').addEventListener('click', () => modelCheck(token));
  form.addEventListener('submit', event => { event.preventDefault(); return submit(); });
  prompt.addEventListener('input', controls);
  prompt.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit(); } });
  cancel.addEventListener('click', () => { if (!busy) return; generation++; if (request) request.abort(); request = null; busy = false; controls(); status.textContent = 'Espera cancelada. O servidor pode continuar a processar; aguarda antes de reenviar.'; });
  el('new-chat').addEventListener('click', () => { clearConversation('Nova conversa iniciada. O contexto anterior foi limpo desta página.'); if (ready) prompt.focus(); });
  el('clear-session').addEventListener('click', () => disconnect());
  for (const item of document.querySelectorAll('[data-prompt]')) item.addEventListener('click', () => { if (busy) return; prompt.value = item.dataset.prompt; controls(); if (ready) prompt.focus(); });
  window.addEventListener('pagehide', () => disconnect()); window.addEventListener('focus', expires);
  window.addEventListener('pageshow', expires); document.addEventListener('visibilitychange', expires);
  if (!local) { connectionStatus.textContent = 'Abre esta página pela API em http://127.0.0.1:PORTA/app, sem parâmetros no endereço.'; guideReason = 'browser'; guide(); return; }
  input.disabled = false; connect.disabled = false; controls();
})();
