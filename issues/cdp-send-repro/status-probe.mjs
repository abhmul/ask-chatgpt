const endpoint = 'http://127.0.0.1:9222';
const targets = await (await fetch(endpoint + '/json/list')).json();
const pages = targets.filter(t => t.type === 'page' && t.url.includes('/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31'));
async function inspect(t) {
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let seq = 0; const pending = new Map();
  ws.addEventListener('message', ev => { const m=JSON.parse(ev.data); if(m.id && pending.has(m.id)){ const p=pending.get(m.id); pending.delete(m.id); m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result); } });
  await new Promise((res,rej)=>{ws.addEventListener('open',res,{once:true}); ws.addEventListener('error',rej,{once:true});});
  function cdp(method, params={}) { const id=++seq; ws.send(JSON.stringify({id,method,params})); return new Promise((resolve,reject)=>pending.set(id,{resolve,reject})); }
  await cdp('Runtime.enable');
  const r = await cdp('Runtime.evaluate', {returnByValue:true, awaitPromise:true, expression:`(() => { const norm=s=>(s||'').replace(/\\s+/g,' ').trim(); const users=[...document.querySelectorAll('[data-message-author-role="user"]')].map(e=>norm(e.innerText||e.textContent)); const assistants=[...document.querySelectorAll('[data-message-author-role="assistant"]')].map(e=>norm(e.innerText||e.textContent)); return {title:document.title, users:users.length, assistants:assistants.length, latestUser:users.at(-1)||'', latestAssistantLength:(assistants.at(-1)||'').length, stopVisible:!!document.querySelector('button[data-testid="stop-button"]'), model:[...document.querySelectorAll('form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])')].map(e=>norm(e.innerText||e.textContent)).filter(Boolean)}; })()`});
  ws.close();
  return {id:t.id, url:t.url, ...r.result.value};
}
for (const p of pages) console.log(JSON.stringify(await inspect(p)));
