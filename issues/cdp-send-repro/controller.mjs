// Persistent "keep pushing!!" controller (direct CDP).
// Attaches to an EXISTING tab for the target conversation. Each cycle, when the
// conversation is idle, it RELOADS the page (clears SPA staleness, re-hydrates a
// clean composer + model label), then sends exactly one "keep pushing!!", verifies
// a NEW user turn appeared, and waits for the response to finish.
//
// Resilience: transient DOM absences (missing composer, empty model label) are
// NOT fatal — they are tolerated/retried, and recoverable errors trigger a
// re-attach via the supervisor loop. Only a CONTRADICTING model label (a real,
// different model selected) or repeated hard failures halt with an ALERT.
// Logs metadata only (no transcript text). Honors a STOP file.

const endpoint = process.env.CDP_ENDPOINT || 'http://127.0.0.1:9222';
const conversationUrl = process.env.PUSH_URL || 'https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31';
const conversationPath = new URL(conversationUrl).pathname;
const prompt = process.env.PUSH_PROMPT || 'keep pushing!!';
const requireModel = process.env.REQUIRE_MODEL || 'Pro Extended';

const DIR = new URL('.', import.meta.url).pathname;
const STOP_FILE = DIR + 'STOP';
const ALERT_FILE = DIR + 'ALERT';
const STATUS_FILE = DIR + 'status.json';
const LOG_FILE = DIR + 'controller.log';
const NEXT_BIG_FILE = DIR + 'next-big.txt';

// Every BIG_INTERVAL_MS, the next send (at the next idle slot) is the milestone
// "refine/compress/proof-tree" message instead of "keep pushing!!". The due time is
// persisted so a controller restart mid-window does NOT re-fire the milestone.
const BIG_INTERVAL_MS = Number(process.env.BIG_INTERVAL_MS || 2 * 60 * 60 * 1000);
const BIG_MARKER = 'compact proof tree'; // distinctive substring used to verify the send landed
const BIG_MESSAGE = `When you reach a natural stopping point after major milestones are achieved, carefully and rigorously go over the claims you have made and build a compact proof tree with statuses for all our work. Include the different branches we went down, which branches we ruled out, and which we are still working through.

Then compress and refine our understanding of the problem and our approach to make our approach more elegant, conceptually sound, and easier to identify the right approach. This means
- simplify
- clean
- replace with alternate, better methods
- make more elegant
- compress unnecessarily long arguments to shorter, more concise arguments (but still formally rigorous and correct)
- turn unnecessarily specific work into a more general, simpler results or theory

By simplifying and compressing our proof we reveal new ideas, remove unnecessary noise in our formulations, and start to expose the real picture of what is going on.

Then, using the compressed and refined understanding consider connections to methods from geometry (e.g. differential, discrete, and convex), topology (e.g. morse, algebraic), analysis (e.g. differential equations, measure theory, complex analysis, transport), statistics, combinatorics (e.g. probabilistic method, statistical physics, graph theory, ramsey theory), number theory, algebra, and algebraic geometry. If you find a better route than the one we are taking, push down that direction.

Finally, rebuild the proof tree with your compressed and simplified understanding of the problem. Make sure to check your proof tree and claims. Then, pick 3-5 of the most promising directions to go and use a pseudorandom generator to select one of them to push down. File the others in the proof tree, in case we find they are useful later.`;

const POLL_MS = 2000;
const STABLE_MS = 8000;        // !stop + no activity for this long => idle/done
const SEND_VERIFY_MS = 30000;  // new user turn must appear within this window
const COMPOSER_WAIT_MS = 20000; // wait this long for the composer to (re)mount
const HYDRATE_MS = 60000;      // post-reload hydration budget
const STALL_MS = 240000;       // after send: no stop + no change this long => stall (recoverable)
const CDP_TIMEOUT_MS = 45000;  // ride through heavy-but-alive renders; a truly hung renderer is recovered via force-navigate
const MAX_CONSECUTIVE_FAILURES = 12;
const RELOAD_EVERY = Number(process.env.RELOAD_EVERY || 8); // reload page every N turns; otherwise send immediately (short gap). Fewer reloads => less renderer-hang exposure on a heavy page.

import { writeFileSync, appendFileSync, existsSync, readFileSync } from 'node:fs';

const sleep = ms => new Promise(r => setTimeout(r, ms));
const now = () => Date.now();
const iso = () => new Date().toISOString();
const normText = s => (s || '').replace(/\s+/g, ' ').trim();

let iter = 0, sentCount = 0, consecutiveFailures = 0, bigCount = 0;
let nextBigAt = null; // epoch ms when the next milestone message is due

function readNextBigAt() {
  try { if (existsSync(NEXT_BIG_FILE)) return Number(readFileSync(NEXT_BIG_FILE, 'utf8').trim()) || 0; } catch {}
  return null;
}
function writeNextBigAt(ts) { try { writeFileSync(NEXT_BIG_FILE, String(ts)); } catch {} }

function log(msg, extra) {
  const line = `${iso()} ${msg}${extra ? ' ' + JSON.stringify(extra) : ''}`;
  try { appendFileSync(LOG_FILE, line + '\n'); } catch {}
  console.log(line);
}
function writeStatus(obj) {
  try { writeFileSync(STATUS_FILE, JSON.stringify({ ts: iso(), iter, sentCount, ...obj }, null, 2)); } catch {}
}
function alertHalt(reason, extra) {
  log('HALT: ' + reason, extra);
  try { writeFileSync(ALERT_FILE, JSON.stringify({ ts: iso(), reason, iter, sentCount, ...extra }, null, 2)); } catch {}
  writeStatus({ phase: 'halted', reason, ...extra });
  process.exit(2);
}
function checkStop() {
  if (existsSync(STOP_FILE)) { log('STOP file present; exiting'); writeStatus({ phase: 'stopped' }); process.exit(0); }
}

async function json(path, opts = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CDP_TIMEOUT_MS);
  try {
    const res = await fetch(endpoint + path, { ...opts, signal: controller.signal });
    if (!res.ok) throw new Error(`${opts.method || 'GET'} ${path} -> ${res.status} ${await res.text()}`);
    return await res.json();
  } finally { clearTimeout(timer); }
}

class CdpPage {
  constructor(target) {
    this.target = target;
    this.seq = 0;
    this.pending = new Map();
    this.ws = new WebSocket(target.webSocketDebuggerUrl);
    this.ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data);
      if (!m.id || !this.pending.has(m.id)) return;
      const p = this.pending.get(m.id); this.pending.delete(m.id); clearTimeout(p.timer);
      m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
    });
    this.ws.addEventListener('close', () => {
      for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(new Error('CDP websocket closed')); }
      this.pending.clear();
    });
  }
  async open() {
    await new Promise((res, rej) => { this.ws.addEventListener('open', res, { once: true }); this.ws.addEventListener('error', rej, { once: true }); });
    await this.cdp('Runtime.enable');
    await this.cdp('Page.enable');
  }
  cdp(method, params = {}) {
    const id = ++this.seq;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error(`CDP timeout for ${method}`)); }, CDP_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timer });
    });
  }
  async evalValue(expression) {
    const r = await this.cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error('Runtime exception: ' + JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
  close() { try { this.ws.close(); } catch {} }
}

const stateExpr = `(() => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
  const idOf = el => el?.getAttribute('data-message-id') || el?.closest('[data-message-id]')?.getAttribute('data-message-id') || '';
  const userEls = [...document.querySelectorAll('[data-message-author-role="user"]')];
  const asstEls = [...document.querySelectorAll('[data-message-author-role="assistant"]')];
  const users = userEls.map(el => ({ id: idOf(el), text: norm(el.innerText || el.textContent) }));
  const asst = asstEls.map(el => ({ id: idOf(el), len: norm(el.innerText || el.textContent).length }));
  const modelLabels = [...document.querySelectorAll('form:has(#prompt-textarea) button[aria-haspopup="menu"]:not([data-testid])')]
    .map(el => norm(el.innerText || el.textContent)).filter(Boolean);
  return {
    users: users.length,
    assistants: asst.length,
    latestUser: users.at(-1)?.text || '',
    latestUserId: users.at(-1)?.id || '',
    latestAssistantLen: asst.at(-1)?.len || 0,
    latestAssistantId: asst.at(-1)?.id || '',
    stopVisible: !!document.querySelector('button[data-testid="stop-button"]'),
    composer: !!document.querySelector('#prompt-textarea'),
    modelLabels
  };
})()`;

// confirmed: a label matches. violation: labels present but NONE match (real wrong model).
// unknown: no labels (transient during generation/reload) — tolerated, never a halt.
function modelConfirmed(s) { return !requireModel || s.modelLabels.some(l => l === requireModel || l.includes(requireModel)); }
function modelViolation(s) { return !!requireModel && s.modelLabels.length > 0 && !s.modelLabels.some(l => l === requireModel || l.includes(requireModel)); }

// One retry on transient eval failure; a second failure propagates to the supervisor.
async function readState(page) {
  try { return await page.evalValue(stateExpr); }
  catch { await sleep(500); return await page.evalValue(stateExpr); }
}

// A model-label mismatch is only "real" if it PERSISTS. During reload/hydration the
// composer briefly surfaces other controls (e.g. "Extra High" reasoning effort) before
// the model name settles, which previously caused false halts. Returns true ONLY on a
// sustained mismatch (~12s of non-matching, non-empty labels with no Pro Extended).
async function confirmViolation(page) {
  for (let i = 0; i < 6; i++) {
    const s = await readState(page);
    if (modelConfirmed(s)) return false;          // model name appeared -> not a violation
    if (s.modelLabels.length === 0) return false; // unknown/transient -> not a violation
    await sleep(2000);
  }
  return true;
}

async function findPage() {
  const targets = await json('/json/list');
  const matches = targets.filter(t => t.type === 'page' && t.url && (() => { try { return new URL(t.url).pathname === conversationPath; } catch { return false; } })());
  const inspected = [];
  for (const t of matches) {
    const page = new CdpPage(t);
    try { await page.open(); const s = await readState(page); inspected.push({ page, s, score: (modelConfirmed(s) ? 1e6 : 0) + (s.composer ? 1e5 : 0) + s.users }); }
    catch { page.close(); }
  }
  if (inspected.length > 0) {
    inspected.sort((a, b) => b.score - a.score);
    for (const it of inspected.slice(1)) it.page.close();
    return inspected[0];
  }
  // A matching tab exists but its renderer is unresponsive (readState timed out) -> the
  // heavy page hung. Protocol-level commands (Page.navigate) still work even when the
  // renderer JS is blocked, so force a fresh navigation to get a clean renderer.
  if (matches.length > 0) {
    const page = new CdpPage(matches[0]);
    try {
      await page.open();
      log('tab unresponsive (hung renderer); forcing fresh navigation to recover', { url: conversationUrl });
      writeStatus({ phase: 'recovering-renderer' });
      await page.cdp('Page.navigate', { url: conversationUrl });
      const dl = now() + HYDRATE_MS;
      await sleep(3000);
      while (now() < dl) {
        checkStop();
        try {
          const s = await readState(page);
          if (s.composer || s.users > 0 || s.assistants > 0) { log('renderer recovered via navigation', { users: s.users, assistants: s.assistants, model: s.modelLabels }); return { page, s, score: 0 }; }
        } catch {}
        await sleep(2000);
      }
      page.close();
    } catch { try { page.close(); } catch {} }
  }
  return null;
}

// Reload the page and wait for a clean, hydrated, idle state. Only call when idle.
async function reloadAndHydrate(page) {
  log('reloading page to clear staleness', { iter });
  writeStatus({ phase: 'reloading' });
  await page.cdp('Page.reload', { ignoreCache: false });
  const deadline = now() + HYDRATE_MS;
  let s = null;
  await sleep(2000);
  while (now() < deadline) {
    checkStop();
    try { s = await readState(page); } catch { await sleep(1000); continue; }
    // Do NOT halt on a transient label mismatch here — keep polling for the model name
    // to settle. A real model switch is caught by the persistence check below.
    if (s.composer && modelConfirmed(s) && (s.users > 0 || s.assistants > 0) && !s.stopVisible) {
      log('hydrated', { iter, model: s.modelLabels, users: s.users, assistants: s.assistants });
      return s;
    }
    await sleep(1000);
  }
  // Budget expired without ever confirming the model. Only halt if the mismatch is sustained.
  if (s && modelViolation(s) && await confirmViolation(page)) {
    alertHalt('different model selected (not ' + requireModel + ') after reload', { modelLabels: s.modelLabels });
  }
  log('WARNING: hydration incomplete; proceeding with last read', { iter, last: s && { composer: s.composer, modelLabels: s.modelLabels, stopVisible: s.stopVisible } });
  return s || await readState(page);
}

// Wait until idle. requireSawStop=true (after a send): require we OBSERVE generation
// (stop control appears, or assistant content changes) before declaring done — this
// prevents declaring "done" off a stale completed turn. Throws on a true stall (recoverable).
async function waitForIdle(page, requireSawStop) {
  let entry = await readState(page);
  let lastActivity = now();
  let sawStop = false;
  let changed = false;
  let prev = entry;
  while (true) {
    checkStop();
    const s = await readState(page);
    if (modelViolation(s) && await confirmViolation(page)) alertHalt('different model selected (not ' + requireModel + ')', { modelLabels: s.modelLabels, iter });
    if (s.stopVisible) sawStop = true;
    if (s.latestAssistantLen !== entry.latestAssistantLen || s.latestAssistantId !== entry.latestAssistantId || s.assistants !== entry.assistants) changed = true;
    const active = s.stopVisible || s.latestAssistantLen !== prev.latestAssistantLen || s.latestAssistantId !== prev.latestAssistantId || s.assistants !== prev.assistants;
    if (active) lastActivity = now();
    prev = s;
    const idleFor = now() - lastActivity;

    writeStatus({ phase: 'waiting', model: s.modelLabels, users: s.users, assistants: s.assistants,
      latestUser: s.latestUser.slice(0, 40), latestAssistantLen: s.latestAssistantLen,
      stopVisible: s.stopVisible, sawStop, changed, idleForMs: idleFor });

    const generationConfirmed = requireSawStop ? (sawStop || changed) : true;
    if (!s.stopVisible && generationConfirmed && idleFor >= STABLE_MS) return s;

    // Stall: after a send, generation never started and nothing is changing.
    if (requireSawStop && !sawStop && !changed && idleFor >= STALL_MS) {
      throw new Error('no generation started after send (stall)');
    }
    await sleep(POLL_MS);
  }
}

// Fill + submit + verify a NEW user turn appeared carrying `marker`.
// `marker` is a distinctive substring of `text` used for verification — robust for
// long multi-line messages where exact normalized-equality is fragile.
// Returns {ok, after} | {ok:false,...}.
async function sendOnce(page, before, text, marker) {
  const normMarker = normText(marker);
  // Wait for the composer to (re)mount — it un-mounts transiently during transitions.
  const cdl = now() + COMPOSER_WAIT_MS;
  let has = false;
  while (now() < cdl) { const s = await readState(page); if (s.composer) { has = true; break; } await sleep(500); }
  if (!has) return { ok: false, stage: 'composer-wait' };

  const filled = await page.evalValue(`(() => {
    const c = document.querySelector('#prompt-textarea');
    if (!c) return { ok:false, reason:'no composer' };
    const norm = s => (s || '').replace(/\\s+/g,' ').trim();
    c.scrollIntoView({ block:'center' }); c.focus();
    document.execCommand('selectAll'); document.execCommand('delete');
    document.execCommand('insertText', false, ${JSON.stringify(text)});
    c.dispatchEvent(new InputEvent('input', { bubbles:true, inputType:'insertText', data:${JSON.stringify(text)} }));
    return { ok:true, text: norm(c.innerText || c.textContent || c.value || '') };
  })()`);
  // Lenient fill check: composer holds the marker (post-send turn check is authoritative).
  if (!filled.ok || !filled.text.includes(normMarker)) return { ok: false, stage: 'fill', detail: filled && { len: (filled.text || '').length } };
  await sleep(500);
  const clicked = await page.evalValue(`(() => {
    const vis = el => !!el && getComputedStyle(el).display!=='none' && getComputedStyle(el).visibility!=='hidden' && el.getBoundingClientRect().width>0 && el.getBoundingClientRect().height>0;
    const btns = [...document.querySelectorAll('button[data-testid="send-button"], button[aria-label="Send prompt"]')].filter(vis);
    const b = btns.find(x => !(x.disabled || x.getAttribute('aria-disabled')==='true' || x.hasAttribute('disabled')));
    if (!b) return { ok:false, reason:'no enabled send button', count:btns.length };
    b.click(); return { ok:true };
  })()`);
  if (!clicked.ok) return { ok: false, stage: 'click', detail: clicked };

  const deadline = now() + SEND_VERIFY_MS;
  let after;
  while (now() < deadline) {
    after = await readState(page);
    if (after.latestUser.includes(normMarker) && (after.latestUserId !== before.latestUserId || after.users > before.users)) {
      return { ok: true, after };
    }
    await sleep(500);
  }
  return { ok: false, stage: 'verify', detail: after && { latestUserId: after.latestUserId, users: after.users } };
}

// Prepare to send WITHOUT a full reload when possible (short inter-turn gap).
// Reloads only when forced (periodic, every RELOAD_EVERY turns) or when the page
// looks stale (composer absent). Halts on a sustained model mismatch.
async function ensureReady(page, forceReload) {
  if (forceReload) return await reloadAndHydrate(page);
  let s = await readState(page);
  if (modelViolation(s) && await confirmViolation(page)) {
    alertHalt('different model selected (not ' + requireModel + ')', { modelLabels: s.modelLabels, iter });
  }
  if (s.composer) return s; // ready without a reload
  // composer briefly absent — short wait, then reload as a staleness fallback
  const dl = now() + 5000;
  while (now() < dl) { await sleep(500); s = await readState(page); if (s.composer) return s; }
  log('composer absent without reload; reloading (staleness fallback)', { iter });
  return await reloadAndHydrate(page);
}

// One attached session: (reload every N turns / on staleness) -> send -> wait, until
// STOP. Throws on recoverable errors so the supervisor can re-attach.
async function runSession(page) {
  let turnsSinceReload = RELOAD_EVERY; // force a reload on the first cycle (clean start)
  // Let any in-flight response finish before doing anything.
  await waitForIdle(page, false);
  while (true) {
    checkStop();
    const forceReload = turnsSinceReload >= RELOAD_EVERY;
    let state = await ensureReady(page, forceReload);
    if (forceReload) turnsSinceReload = 0;
    iter++;
    if (!modelConfirmed(state)) log('WARNING: model label not confirmed; proceeding on prior confirmation', { iter });

    // Decide message: milestone "refine" message if the 2h window is due, else keep pushing.
    const due = now() >= (nextBigAt ?? 0);
    const messageType = due ? 'milestone' : 'keep-pushing';
    const text = due ? BIG_MESSAGE : 'keep pushing!!';
    const marker = due ? BIG_MARKER : 'keep pushing';

    writeStatus({ phase: 'sending', messageType, reloadedThisTurn: forceReload, nextBigAtIso: nextBigAt ? new Date(nextBigAt).toISOString() : null });
    log('sending', { iter, messageType, reloaded: forceReload, turnsSinceReload, assistants: state.assistants });
    let sent = await sendOnce(page, state, text, marker);
    if (!sent.ok) {
      // staleness fallback: reload and retry once
      log('send failed; reloading and retrying', { iter, stage: sent.stage, messageType });
      state = await reloadAndHydrate(page);
      turnsSinceReload = 0;
      sent = await sendOnce(page, state, text, marker);
    }
    if (!sent.ok) throw new Error('send failed twice: ' + sent.stage); // recoverable -> re-attach

    sentCount++;
    consecutiveFailures = 0;
    turnsSinceReload++;
    if (due) {
      bigCount++;
      nextBigAt = now() + BIG_INTERVAL_MS;
      writeNextBigAt(nextBigAt);
      log('milestone message sent; next milestone due', { bigCount, nextBigAtIso: new Date(nextBigAt).toISOString() });
    }
    log('send verified; waiting for response', { iter, sentCount, messageType, newUserId: sent.after.latestUserId });
    writeStatus({ phase: 'sent', messageType, bigCount, nextBigAtIso: nextBigAt ? new Date(nextBigAt).toISOString() : null });

    const done = await waitForIdle(page, true);
    log('response complete', { iter, sentCount, assistants: done.assistants, latestAssistantLen: done.latestAssistantLen });
  }
}

async function main() {
  if (existsSync(STOP_FILE)) alertHalt('STOP file present at startup; remove it to run');
  // Load the persisted milestone due-time. If none, default to 0 => the FIRST send is
  // the milestone message ("starting now"); subsequent ones advance by BIG_INTERVAL_MS.
  nextBigAt = readNextBigAt();
  if (nextBigAt === null) { nextBigAt = 0; writeNextBigAt(0); }
  log('controller starting', { conversationPath, requireModel, bigIntervalMs: BIG_INTERVAL_MS, nextBigAtIso: nextBigAt ? new Date(nextBigAt).toISOString() : 'due-now' });
  while (true) {
    checkStop();
    let found = null;
    try { found = await findPage(); } catch (e) { log('findPage error', { err: String(e && e.message || e) }); }
    if (!found) {
      consecutiveFailures++;
      writeStatus({ phase: 'reattaching', consecutiveFailures });
      log('no conversation tab; will retry', { consecutiveFailures });
      if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) alertHalt('no conversation tab after repeated retries');
      await sleep(5000); continue;
    }
    const page = found.page;
    if (modelViolation(found.s) && await confirmViolation(page)) alertHalt('different model selected (not ' + requireModel + ') on existing tab', { modelLabels: found.s.modelLabels });
    log('attached to tab', { model: found.s.modelLabels, users: found.s.users, assistants: found.s.assistants, stopVisible: found.s.stopVisible });
    try {
      await runSession(page); // only returns by process.exit on STOP
    } catch (e) {
      consecutiveFailures++;
      log('session error; re-attaching', { err: String(e && e.message || e), consecutiveFailures });
      try { page.close(); } catch {}
      if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) alertHalt('repeated session errors', { err: String(e && e.message || e) });
      await sleep(4000);
      continue;
    }
  }
}

main().catch(e => alertHalt('uncaught: ' + (e && e.stack ? e.stack : String(e))));
