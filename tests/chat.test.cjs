// Exercises actual app.js control flow with a small DOM fixture. Not browser/layout QA.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../gensia/web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../gensia/web/app.html'), 'utf8');
const TOKEN = 'synthetic'.repeat(8);
const response = (value, status=200) => new Response(JSON.stringify(value), {status, headers:{'content-type':'application/json'}});
const model = () => response({configured:true, available:true, locality:'confirmed_local', inference_tested:false});
const reply = text => response({reply:text, actions_executed:false, cloud_fallback:false});

function setup(fetcher=(url)=>url==='/model' ? model() : reply('Resposta sintética'), location={}) {
  class Element {
    constructor() { this.value=''; this.textContent=''; this.hidden=false; this.disabled=false; this.handlers={}; this.children=[]; this.lastChild={textContent:''}; this.classList={remove(){},toggle(){}}; }
    addEventListener(name, handler) {this.handlers[name]=handler;}
    replaceChildren(...items) {this.children=items;}
    appendChild(child) {child.parent=this;this.children.push(child);}
    setAttribute() {}
    focus() {}
    get firstElementChild() {return this.children[0];}
    remove() {this.parent.children.splice(this.parent.children.indexOf(this),1);}
    set innerHTML(_) {throw new Error('HTML injection sink forbidden');}
  }
  const elements=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(match=>[match[1],new Element()]));
  for (const id of ['prompt','send','api-token','connect']) elements[id].disabled=true;
  elements.messages.hidden=true;
  const events={}, documentEvents={}, calls=[], timers=[], clock={wall:1700000000000, monotonic:0};
  const document={getElementById(id){assert.ok(elements[id]);return elements[id];},createElement(){return new Element();},querySelectorAll(){return [];},addEventListener(name,handler){documentEvents[name]=handler;}};
  const window={location:{protocol:'http:',hostname:'127.0.0.1',search:'',hash:'',username:'',password:'',...location},addEventListener(name,handler){events[name]=handler;}};
  const context={window,document,AbortController,TextDecoder,TextEncoder,
    Date:{now:()=>clock.wall},performance:{now:()=>clock.monotonic},
    fetch:async(...args)=>{calls.push(args);return fetcher(...args);},
    setTimeout(cb,ms){const timer={cb,ms};timers.push(timer);return timer;},clearTimeout(timer){if(timer)timer.cleared=true;}};
  for (const scope of [window,context]) for (const name of ['localStorage','sessionStorage']) Object.defineProperty(scope,name,{get(){throw new Error('Persistence forbidden');}});
  vm.runInNewContext(source,context,{timeout:1000});
  return {elements,events,documentEvents,calls,timers,clock,
    connect(value=TOKEN){elements['api-token'].value=value;return elements['connect-form'].handlers.submit({preventDefault(){}});},
    send(text){elements.prompt.value=text;return elements['chat-form'].handlers.submit({preventDefault(){}});}};
}

test('shell stays offline until explicit connection; token only enters authorization header',async()=>{
  const ui=setup();assert.equal(ui.calls.length,0);assert.equal(ui.elements.prompt.disabled,true);
  await ui.connect();assert.equal(ui.elements['api-token'].value,'');assert.equal(ui.elements.prompt.disabled,false);
  await ui.send('Olá');
  assert.deepEqual(ui.calls.map(call=>call[0]),['/model','/chat']);
  for(const [url,options] of ui.calls){assert.equal(options.headers.Authorization,'Bearer '+TOKEN);assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');assert.ok(!url.includes(TOKEN));}
  assert.ok(!ui.calls[1][1].body.includes(TOKEN));
});

test('long valid assistant replies survive follow-up; oldest whole pairs trim by character limit',async()=>{
  const ui=setup(url=>url==='/model'?model():reply('a'.repeat(8000)));await ui.connect();
  await ui.send('primeira');await ui.send('segunda');
  let body=JSON.parse(ui.calls.at(-1)[1].body);assert.equal(body.messages.length,3);assert.equal(body.messages[1].content.length,8000);
  await ui.send('terceira');body=JSON.parse(ui.calls.at(-1)[1].body);
  assert.deepEqual(body.messages.map(item=>item.content.length),[7,8000,8]);
  assert.deepEqual(body.messages.map(item=>item.role),['user','assistant','user']);
});

test('UTF-8 body limit trims old whole pairs even below context character limit',async()=>{
  const ui=setup(url=>url==='/model'?model():reply('漢'.repeat(8000)));await ui.connect();
  await ui.send('q');await ui.send('漢'.repeat(3999));
  const body=JSON.parse(ui.calls.at(-1)[1].body);assert.equal(body.messages.length,1);
  assert.ok(Buffer.byteLength(ui.calls.at(-1)[1].body)<=32768);
});

test('untrusted output is text and overlong replies never enter history',async()=>{
  let text='<img src=x onerror=alert(1)>';
  const ui=setup(url=>url==='/model'?model():reply(text));await ui.connect();await ui.send('q');
  assert.equal(ui.elements.messages.children[1].children[1].children[1].textContent,text);
  text='x'.repeat(8001);await ui.send('too long');assert.equal(ui.elements.messages.children.length,3);
  assert.match(ui.elements['request-status'].textContent,/espera terminou/);
});

test('cancel ignores an upstream late reply and new conversation removes context',async()=>{
  let resolve, delay=true;
  const ui=setup(url=>url==='/model'?model():delay?new Promise(done=>{resolve=done;}):reply('ok'));
  await ui.connect();const pending=ui.send('q');ui.elements.cancel.handlers.click();
  assert.equal(ui.calls.at(-1)[1].signal.aborted,true);resolve(reply('LATE PRIVATE'));await pending;
  assert.equal(ui.elements.messages.children.length,1);assert.match(ui.elements['request-status'].textContent,/servidor pode continuar/);
  ui.elements['new-chat'].handlers.click();assert.equal(ui.elements.messages.children.length,0);
  delay=false;await ui.send('novo');assert.equal(JSON.parse(ui.calls.at(-1)[1].body).messages.length,1);
});

test('logout during request clears all state and prevents late token reuse',async()=>{
  let resolve;const ui=setup(url=>url==='/model'?model():new Promise(done=>{resolve=done;}));
  await ui.connect();const pending=ui.send('q');ui.elements['clear-session'].handlers.click();resolve(reply('PRIVATE'));await pending;
  assert.equal(ui.elements.messages.children.length,0);assert.equal(ui.elements.prompt.disabled,true);
  await ui.elements['check-model'].handlers.click();await ui.send('should not send');assert.equal(ui.calls.length,2);
});

test('401 clears session without reading or reflecting raw upstream error',async()=>{
  const ui=setup(url=>url==='/model'?model():new Response('PRIVATE '+TOKEN,{status:401}));
  await ui.connect();await ui.send('q');assert.equal(ui.elements.messages.children.length,0);
  assert.match(ui.elements['connection-status'].textContent,/Token recusado/);assert.doesNotMatch(ui.elements['connection-status'].textContent,/PRIVATE|synthetic/);
});

test('expiry and backward wall-clock adjustment invalidate local session',async()=>{
  for(const delta of [300000,-1]){
    const ui=setup();await ui.connect();await ui.send('q');ui.clock.wall+=delta;
    if(delta>0)ui.clock.monotonic+=delta;
    ui.events.focus();assert.equal(ui.elements.messages.children.length,0);assert.equal(ui.elements.prompt.disabled,true);
    assert.match(ui.elements['connection-status'].textContent,/expirada/);await ui.send('blocked');assert.equal(ui.calls.length,2);
  }
});

test('non-local URLs and embedded credentials disable connection without network calls',()=>{
  for(const location of [{protocol:'file:'},{hostname:'localhost'},{search:'?token=x'},{hash:'#x'},{username:'user'},{password:'secret'}]){
    const ui=setup(undefined,location);assert.equal(ui.elements['api-token'].disabled,true);assert.equal(ui.calls.length,0);
  }
});

test('unsafe or excessive user text never reaches provider',async()=>{
  const ui=setup();await ui.connect();for(const text of ['x'.repeat(4001),'\x1bPRIVATE','\ud800'])await ui.send(text);
  assert.equal(ui.calls.length,1);assert.equal(ui.elements.messages.children.length,0);
});
