/* Real browser QA; the running application receives a clearly synthetic provider. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const outputArgument = process.argv[2] === '--output' ? process.argv[3] : process.argv[2];

async function main() {
  const output = path.resolve(outputArgument || 'artifacts/chat-browser');
  if (fs.existsSync(output)) throw new Error('evidence_directory_exists');
  fs.mkdirSync(output, {recursive:true});
  const report = {kind:'gensia.chat_browser_qa', passed:false, synthetic_model:true,
    real_inference_tested:false, screenshots:[], checks:[], blocked_reason:null};
  const save = () => fs.writeFileSync(path.join(output,'validation.json'), JSON.stringify(report,null,2)+'\n');
  let browser, child;
  try {
    let playwright;
    try { playwright = require('playwright'); }
    catch {
      if (!process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES) throw new Error('playwright_unavailable');
      playwright = require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'playwright'));
    }
    if (!fs.existsSync(playwright.chromium.executablePath())) {
      report.blocked_reason='chromium_unavailable'; save(); return 2;
    }
    const token=crypto.randomBytes(32).toString('hex');
    const env={GENSIA_API_TOKEN:token};
    for (const key of ['PATH','SYSTEMROOT','WINDIR','TEMP','TMP','TMPDIR']) {
      if (process.env[key]) env[key]=process.env[key];
    }
    child=spawn(process.env.GENSIA_PYTHON || 'python', ['-I','-B',path.join(__dirname,'chat_test_server.py')],
      {env,stdio:['ignore','pipe','ignore']});
    const port=await new Promise((resolve,reject) => {
      let text=''; const timer=setTimeout(() => reject(new Error('test_server_timeout')),10000);
      child.once('error',() => {clearTimeout(timer);reject(new Error('test_server_unavailable'));});
      child.once('exit',() => {clearTimeout(timer);reject(new Error('test_server_exit'));});
      child.stdout.on('data', data => {
        text+=data.toString('utf8');
        if (text.length>2048) {clearTimeout(timer);reject(new Error('test_server_invalid'));return;}
        if (!text.includes('\n')) return;
        try {
          const event=JSON.parse(text.trim().split('\n')[0]);
          if (event.event!=='listening' || !Number.isInteger(event.port) || event.port<1024 || event.port>65535) throw new Error();
          clearTimeout(timer);resolve(event.port);
        } catch {clearTimeout(timer);reject(new Error('test_server_invalid'));}
      });
    });
    const origin=`http://127.0.0.1:${port}`;
    for (let retry=0;retry<50;retry++) {
      try {if ((await fetch(origin+'/health',{headers:{Authorization:'Bearer '+token}})).ok) break;}
      catch {}
      if (retry===49) throw new Error('test_server_not_ready');
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    browser=await playwright.chromium.launch({headless:true});
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*', route => {
      const url=new URL(route.request().url());
      return url.origin===origin && !url.search ? route.continue() : route.abort('blockedbyclient');
    });
    const page=await context.newPage();
    const errors=[];page.on('pageerror',()=>errors.push('page_error'));
    await page.goto(origin+'/app');
    await page.locator('#api-token').waitFor({state:'visible'});
    assert.equal(await page.locator('#prompt').isDisabled(),true);
    assert.equal(await page.locator('#setup-progress').innerText(),'0 de 3 passos');
    await page.locator('#setup-guide summary').click();
    await page.screenshot({path:path.join(output,'setup-initial.png'),fullPage:true});
    report.screenshots.push('setup-initial.png');
    await page.setViewportSize({width:390,height:1000});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(output,'setup-390.png'),fullPage:true});
    report.screenshots.push('setup-390.png');
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('#setup-guide summary').click();
    await page.locator('#api-token').fill(token);
    await page.locator('#connect').click();
    await page.waitForFunction(()=>!document.querySelector('#prompt').disabled);
    assert.equal(await page.locator('#api-token').inputValue(),'');
    assert.equal(await page.locator('#setup-progress').innerText(),'2 de 3 passos');
    assert.equal(await page.locator('#setup-reply').innerText(),'Por testar');
    await page.locator('#setup-guide summary').click();
    await page.screenshot({path:path.join(output,'setup-model-ready.png'),fullPage:true});
    report.screenshots.push('setup-model-ready.png');
    await page.locator('#setup-guide summary').click();
    report.checks.push('setup_metadata_does_not_claim_inference_and_responsive_instructions');
    report.checks.push('connection_and_token_field_cleared');
    async function send(text, expected) {
      await page.locator('#prompt').fill(text);await page.locator('#send').click();
      await page.waitForFunction(()=>!document.querySelector('#prompt').disabled);
      if (expected) assert.match(await page.locator('.message.assistant').last().innerText(),expected);
    }
    await send('Explica DNS com um exemplo prático.', /Contexto: 1 mensagens/);
    assert.equal(await page.locator('#setup-progress').innerText(),'3 de 3 passos');
    await send('Como funciona o cache?', /Contexto: 3 mensagens/);
    report.checks.push('conversation_and_followup_context');
    await page.screenshot({path:path.join(output,'chat-desktop.png'),fullPage:true});
    report.screenshots.push('chat-desktop.png');
    for (const width of [768,390,320]) {
      await page.setViewportSize({width,height:1000});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      assert.equal(await page.locator('#prompt').isVisible(),true);
      await page.screenshot({path:path.join(output,`chat-${width}.png`),fullPage:true});
      report.screenshots.push(`chat-${width}.png`);
    }
    report.checks.push('responsive_768_390_320_no_horizontal_overflow');
    await send('SIMULATE_HTML', /<img src=x/);
    assert.equal(await page.locator('#messages img').count(),0);
    assert.equal(await page.evaluate(()=>window.__injected),undefined);
    report.checks.push('model_html_rendered_as_text');
    await send('SIMULATE_ERROR');
    assert.match(await page.locator('#request-status').innerText(),/processamento remoto/);
    report.checks.push('safe_model_error_feedback');
    await page.locator('#prompt').fill('SIMULATE_SLOW');await page.locator('#send').click();
    await page.locator('#cancel').click();
    assert.match(await page.locator('#request-status').innerText(),/servidor pode continuar/);
    const messages=await page.locator('.message.assistant').count();
    await page.waitForTimeout(1500);
    assert.equal(await page.locator('.message.assistant').count(),messages);
    report.checks.push('cancel_wait_and_ignore_late_reply');
    await page.locator('#new-chat').click();
    assert.equal(await page.locator('.message').count(),0);
    assert.equal(await page.locator('#setup-progress').innerText(),'2 de 3 passos');
    await send('Uma conversa nova.', /Contexto: 1 mensagens/);
    report.checks.push('new_conversation_removes_previous_context');
    assert.deepEqual(await context.cookies(),[]);
    assert.deepEqual(await page.evaluate(()=>[localStorage.length,sessionStorage.length]),[0,0]);
    await page.locator('#clear-session').click();
    assert.equal(await page.locator('.message').count(),0);
    assert.equal(await page.locator('#prompt').isDisabled(),true);
    assert.equal(await page.locator('#setup-progress').innerText(),'0 de 3 passos');
    await page.locator('#api-token').fill('b'.repeat(64));await page.locator('#connect').click();
    await page.waitForFunction(()=>document.querySelector('#connection-status').textContent.includes('recusado'));
    report.checks.push('clear_session_no_storage_and_invalid_token');
    // Explicitly synthetic error response for the frontend recovery instructions.
    await page.route('**/model', route => route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({error:'model_not_found',message:'UNTRUSTED_DIAGNOSTIC'})}));
    await page.locator('#api-token').fill(token);await page.locator('#connect').click();
    await page.waitForFunction(()=>document.querySelector('#setup-hint').textContent.includes('ollama list'));
    assert.equal(await page.locator('#setup-progress').innerText(),'0 de 3 passos');
    assert.equal(await page.locator('#prompt').isDisabled(),true);
    assert.equal(await page.locator('#setup-guide').evaluate(element=>element.open),true);
    assert.doesNotMatch(await page.locator('#setup-hint').innerText(),/UNTRUSTED/);
    await page.screenshot({path:path.join(output,'setup-model-missing.png'),fullPage:true});
    report.screenshots.push('setup-model-missing.png');
    await page.unroute('**/model');
    report.checks.push('setup_error_instructions_and_progress_reset_with_synthetic_error');
    assert.deepEqual(errors,[]);
    report.passed=true;save();return 0;
  } catch (error) {
    report.blocked_reason='browser_check_or_setup_failed';save();return 2;
  } finally {
    if (browser) await browser.close();
    if (child && child.exitCode===null) {
      child.kill('SIGTERM');
      await Promise.race([new Promise(resolve=>child.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,3000))]);
      if (child.exitCode===null) child.kill('SIGKILL');
    }
  }
}
main().then(code=>{console.log(JSON.stringify({evidence:path.resolve(outputArgument || 'artifacts/chat-browser'),exit_code:code}));process.exitCode=code;},()=>{console.error('chat_browser_qa_failed');process.exitCode=2;});
