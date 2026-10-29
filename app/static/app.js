/* Kreola Review: screens (Overview, Review, Learning), word card, autosave, voice notes. No build step. */
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const hm = h => `${Math.floor(h)} h ${String(Math.round(h % 1 * 60)).padStart(2, '0')}`;  // non-breaking: "10 h 02" never splits
const phone = () => matchMedia('(max-width:720px)').matches;
const LANG = {mfe_Latn: 'Kreol', fra_Latn: 'French', eng_Latn: 'English'};
const DIFF = {hard: 'Hard', typ: 'Typical', easy: 'Easy'};
const nice = s => { s = String(s).replace(/_/g, ' '); return s[0].toUpperCase() + s.slice(1); };
const langs = e => (e.languages || [e.language]).map(l => LANG[l] || l).join(' + ');
const WORD_WHY = ['Misheard', 'Spelling', 'Can’t hear', 'Wrong language', 'Timing off'];
const CLIP_WHY = ['Can’t hear', 'Timing off', 'Wrong language', 'Music behind', 'Several speakers'];

async function api(path, opt = {}) {
  const r = await fetch('api/' + path, {headers: opt.body && !(opt.body instanceof FormData) ? {'Content-Type': 'application/json'} : {}, ...opt,
    body: opt.body && !(opt.body instanceof FormData) ? JSON.stringify(opt.body) : opt.body});
  if (r.status === 401 && path !== 'login') { login(); throw new Error('login'); }
  if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) {} throw new Error(d || `Error ${r.status}`); }
  return r.headers.get('content-type')?.includes('json') ? r.json() : r.text();
}
function toast(t) { $('#toastT').textContent = t; $('#toast').classList.add('on'); clearTimeout(toast.h); toast.h = setTimeout(() => $('#toast').classList.remove('on'), 1800); }

/* ───── routing ───── */
let OV = null;
async function route() {
  closeCard(); stopAudio();
  const h = location.hash.replace(/^#\/?/, '').split('/');
  $$('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === ({r: 'review', review: 'review', learning: 'learning'}[h[0]] || 'overview')));
  if (h[0] !== 'c') filter = 'all';
  try {
    if (h[0] === 'learning') return learning();
    if (h[0] === 'c' && h[1]) return category(decodeURIComponent(h[1]));
    if (h[0] === 'r' && h[1]) return review(decodeURIComponent(h[1]), +h[2] || 0);
    if (h[0] === 'review') { OV = await api('overview'); const n = nextUp(OV); return n ? (location.hash = `#/r/${n.id}`) : overview(); }
    return overview();
  } catch (e) { if (e.message !== 'login') $('#main').innerHTML = `<div class="card" style="margin-top:24px">Something went wrong: ${esc(e.message)}</div>`; }
}
addEventListener('hashchange', route);
function nextUp(ov, cat) { const xs = ov.excerpts.filter(e => !cat || e.category === cat); return xs.find(e => e.status === 'half') || xs.find(e => e.status === 'todo'); }
function pill(ov) { $('#pill').innerHTML = `<b>${hm(ov.hours_done)}</b> of ${Math.round(ov.hours_total)} h reviewed`; }

/* ───── login ───── */
function login() {
  $('#top').hidden = true;
  $('#main').innerHTML = `<div class="card login screen"><h1>Kreola Review</h1><p class="sub">Enter the password to continue.</p>
    <form id="lf"><div class="field"><input type="password" id="pw" placeholder="Password" autocomplete="current-password"></div>
    <div class="err" id="lerr"></div><button class="btn primary" style="width:100%">Sign in</button></form></div>`;
  $('#pw').focus();
  $('#lf').onsubmit = async ev => { ev.preventDefault();
    try { await api('login', {method: 'POST', body: {password: $('#pw').value}}); start(); } catch (e) { $('#lerr').textContent = 'Wrong password'; } };
}

/* ───── overview ───── */
const COL = ['#6B7F6E', '#A7B8A7', '#C9BDAF', '#8FA394', '#DCCFBF'];
let filter = 'all', shown = 40;
async function overview() {
  const ov = OV = await api('overview'); pill(ov);
  const pct = Math.round(ov.hours_done / ov.hours_total * 100), next = nextUp(ov), hour = new Date().getHours();
  // time left = your reviewing time per hour of audio so far x audio left (shown once there is enough to measure)
  const pace = ov.hours_done * 60 >= 2 && ov.work_hours > 0 ? ov.work_hours / ov.hours_done * (ov.hours_total - ov.hours_done) : 0;
  const dur = h => h * 60 < 60 ? `${Math.round(h * 60)} min` : hm(h);
  const fams = Object.entries(ov.total_hours).filter(([k]) => ov.excerpts.some(e => e.family === k)).sort((a, b) => b[1] - a[1]);
  const famTot = fams.reduce((a, [, h]) => a + h, 0);
  const row = (label, k) => { const d = ov.done_hours[k] || 0, t = ov.total_hours[k] || 0;
    return `<div class="rowbar"><span>${label}</span><div class="bar"><i style="width:${t ? d / t * 100 : 0}%"></i></div><span class="n">${d.toFixed(1)} / ${t.toFixed(1)} h</span></div>`; };
  $('#main').innerHTML = `<section class="screen">
  <div class="card hero">
    <div class="hhead">
      <div class="ring"><svg viewBox="0 0 150 150"><circle cx="75" cy="75" r="62" fill="none" stroke="#E7E1D8" stroke-width="14"/>
        <circle cx="75" cy="75" r="62" fill="none" stroke="#6B7F6E" stroke-width="14" stroke-linecap="round" stroke-dasharray="390" stroke-dashoffset="${390 - 390 * Math.max(pct, .5) / 100}"/></svg>
        <div class="v"><b>${pct}%</b></div></div>
      <div class="hi"><h1>Good ${hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'}, ${esc(ov.name)}</h1>
        <p class="sub"><b>${hm(ov.hours_done)}</b> of ${Math.round(ov.hours_total)} h reviewed · ${hm(ov.hours_total - ov.hours_done)} to go</p></div>
    </div>
    <div class="kpis">
      <div><b>${dur(ov.today_hours)}</b><span>Today</span></div>
      <div><b>${ov.words_fixed.toLocaleString()}</b><span>Words fixed</span></div>
      <div><b>${ov.voice_notes}</b><span>Voice notes</span></div>
      <div title="Time you spend per hour of audio, so far, times the audio left">${pace ? `<b>≈ ${Math.round(pace)} h</b><span>Left at your pace</span>` : '<b>—</b><span>Pace after a few clips</span>'}</div>
    </div>
    ${next ? `<a class="upnext" href="#/r/${encodeURIComponent(next.id)}">
      <span class="pdot"><svg width="16" height="16" viewBox="0 0 20 20"><path d="M6 3.5v13l11-6.5z" fill="currentColor"/></svg></span>
      <span class="ut"><small>${next.status === 'half' ? 'Continue' : 'Up next'} · ${nice(next.category)}</small><b>${esc(next.title)}</b>
        <span class="meta"><span><span class="dot ${next.difficulty}"></span>${DIFF[next.difficulty]}</span><i></i><span>${langs(next)}</span><i></i><span>${fmt(next.duration)}</span>${next.status === 'half' ? `<i></i><span>${next.done}/${next.clips} clips</span>` : ''}</span></span>
      <span class="go">${next.status === 'half' ? 'Continue' : 'Start'} →</span></a>` : '<div class="upnext"><span class="ut"><small>All done</small><b>Every recording is reviewed 🎉</b></span></div>'}
  </div>
  <div class="grid two" style="margin-top:20px">
    <div class="card"><h2>Your ${Math.round(ov.hours_total)} hours</h2>
      <div class="stack">${fams.map(([f, h], i) => `<i style="flex:${h};background:${COL[i % 5]}"><em class="tip">${nice(f)} · ${Math.round(h / famTot * 100)}% · ${hm(h)}</em></i>`).join('')}</div>
      <div class="legend">${fams.map(([f, h], i) => `<span><em style="background:${COL[i % 5]}"></em>${nice(f)} <b>${Math.round(h / famTot * 100)}%</b></span>`).join('')}</div></div>
    <div class="card"><h2>Progress by mix</h2>${row('Kreol', 'mfe_Latn')}${row('French', 'fra_Latn')}${row('English', 'eng_Latn')}<div style="height:8px"></div>
      ${row('<span class="dot hard"></span>Hard', 'hard')}${row('<span class="dot typ"></span>Typical', 'typ')}${row('<span class="dot easy"></span>Easy', 'easy')}</div>
  </div>
  <div class="card" style="margin-top:20px"><h2>Recordings by category</h2><div id="cats"></div></div></section>`;
  $$('.stack i').forEach(el => el.onclick = () => { const on = el.classList.contains('on'); $$('.stack i').forEach(x => x.classList.remove('on')); if (!on) el.classList.add('on'); });
  cats();
}
/* categories: tiles grouped by family, each with its clip progress; a tile opens the category page */
function catStats() {
  const c = {};
  for (const e of OV.excerpts) {
    const x = c[e.category] ??= {cat: e.category, family: e.family, recs: 0, recsDone: 0, clips: 0, clipsDone: 0, hours: 0};
    x.recs++; x.recsDone += e.status === 'done'; x.clips += e.clips; x.clipsDone += e.done; x.hours += e.duration / 3600;
  }
  return Object.values(c);
}
function cats() {
  const st = catStats(), fams = {};
  st.forEach(x => (fams[x.family] ??= []).push(x));
  const order = Object.entries(fams).sort((a, b) => b[1].reduce((s, x) => s + x.hours, 0) - a[1].reduce((s, x) => s + x.hours, 0));
  $('#cats').innerHTML = order.map(([f, xs]) => `<div class="fam"><h3>${nice(f)}</h3><div class="tiles">${xs.sort((a, b) => b.hours - a.hours).map(x => {
    const p = Math.round(x.clipsDone / x.clips * 100);
    return `<a class="tile ${p === 100 ? 'done' : ''}" href="#/c/${encodeURIComponent(x.cat)}"><b>${nice(x.cat)}</b>
      <span class="tm">${x.recs} recording${x.recs > 1 ? "s" : ""} · ${hm(x.hours)}</span><div class="bar"><i style="width:${p}%"></i></div>
      <span class="tp">${p === 100 ? '✓ Done' : p ? `${p}% · ${x.recsDone} of ${x.recs} done` : 'Not started'}</span></a>`; }).join('')}</div></div>`).join('');
}
/* one category: every recording in it, with what is done and what is not */
async function category(cat) {
  OV = await api('overview'); pill(OV);
  const x = catStats().find(s => s.cat === cat);
  if (!x) return (location.hash = '#/');
  const next = nextUp(OV, cat), p = Math.round(x.clipsDone / x.clips * 100);
  $('#main').innerHTML = `<section class="screen">
  <div class="rvhead"><a class="back" href="#/"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>Overview</a>
    <h1>${nice(cat)}</h1><div class="meta" style="margin-top:6px"><span>${nice(x.family)}</span><i></i><span>${x.recs} recording${x.recs > 1 ? "s" : ""}</span><i></i><span>${hm(x.hours)}</span><i></i><span>${x.clips} clips</span></div></div>
  <div class="card catbar"><div style="flex:1"><div class="rowbar" style="margin:0;grid-template-columns:1fr 150px"><div class="bar"><i style="width:${p}%"></i></div><span class="n">${x.clipsDone} of ${x.clips} clips · ${p}%</span></div></div>
    ${next ? `<a class="btn primary" href="#/r/${encodeURIComponent(next.id)}">${next.status === 'half' ? 'Continue' : 'Start'} →</a>` : '<span class="tag">✓ All done</span>'}</div>
  <div class="card" style="margin-top:20px">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap"><h2 style="margin:0">Recordings</h2>
      <div class="seg" id="filter" style="margin-left:auto">${[['all', 'All'], ['todo', 'To do'], ['half', 'Started'], ['done', 'Done']].map(([k, l]) => `<button data-f="${k}" class="${filter === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>
    <div class="list" id="list"></div><div class="more" id="more"></div>
  </div></section>`;
  $$('#filter button').forEach(b => b.onclick = () => { filter = b.dataset.f; shown = 40; $$('#filter button').forEach(y => y.classList.toggle('on', y === b)); list(cat); });
  list(cat);
}
function list(cat) {
  const all = OV.excerpts.filter(e => e.category === cat && (filter === 'all' || e.status === filter));
  $('#list').innerHTML = all.slice(0, shown).map(e => `<a class="item" href="#/r/${encodeURIComponent(e.id)}">
    <span class="st ${e.status}">${e.status === 'done' ? '✓' : ''}</span>
    <div><div class="t">${esc(e.title)}</div><div class="meta"><span>${e.done}/${e.clips} clips</span><i></i><span><span class="dot ${e.difficulty}"></span>${DIFF[e.difficulty]}</span><i></i><span>${langs(e)}</span></div></div>
    <span class="d">${fmt(e.duration)}</span></a>`).join('') || '<p class="empty">Nothing here yet.</p>';
  $('#more').innerHTML = all.length > shown ? `<button class="btn ghost small">Show more (${all.length - shown})</button>` : '';
  if (all.length > shown) $('#more button').onclick = () => { shown += 60; list(cat); };
}

/* ───── review ───── */
const audio = new Audio(); audio.preload = 'auto';
let EX = null, cur = 0, stopAt = null, heardJ = null, clipT0 = Date.now(), lastTap = {};
function stopAudio() { audio.pause(); stopAt = null; heardJ = null; }
const C = () => EX.clips[cur];
const S = () => C().state || (C().state = {edits: {}, why: [], note: '', verdict: null});
const shown_ = (t, i) => { const e = S().edits[i] || {}; return e.show ?? t.auto ?? t.t; };
const wordVoice = i => C().voice.filter(v => v.word === i);
const flagged = i => { const e = S().edits[i] || {}; return (e.why || []).length || e.note || wordVoice(i).length; };
const touched = c => c.state && (Object.keys(c.state.edits || {}).length || (c.state.why || []).length || c.state.note);
const mine = (t, i) => { const e = S().edits[i] || {}; return e.gone || (e.show != null && e.show !== (t.auto ?? t.t)); };

async function review(id, start) {
  if (!OV) OV = await api('overview');
  pill(OV);
  EX = await api('excerpt/' + encodeURIComponent(id));
  audio.src = 'api/audio/' + encodeURIComponent(id);
  const first = EX.clips.findIndex(c => !c.state?.verdict);
  cur = start || (first < 0 ? 0 : first);
  $('#main').innerHTML = `<section class="screen">
  <div class="rvbar" id="rvbar">
    <a class="back" href="#/c/${encodeURIComponent(EX.category)}" title="Back to ${nice(EX.category)}"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg><span>${nice(EX.category)}</span></a>
    <div class="rvt" title="${esc(EX.title)}"><b>${esc(EX.title)}</b><span class="meta"><span>${fmt(EX.duration)}</span><i></i><span><span class="dot ${EX.difficulty}"></span>${DIFF[EX.difficulty]}</span><i></i><span>${langs(EX)}</span></span></div>
    <div class="rvnav"><button class="nb" id="prevc" aria-label="Previous clip">‹</button><span id="clipno"></span><button class="nb" id="nextc" aria-label="Next clip">›</button></div>
    <button class="btn quiet helpbtn" id="helpbtn">Translate</button>
    <button class="btn quiet" id="skip">Skip</button>
    <button class="btn primary" id="ok">✓ <span id="okl">Clip is correct</span></button>
  </div>
  <div class="rv">
    <nav class="card rail" id="rail" aria-label="Clips"></nav>
    <div class="card" id="clipcard"></div>
    <aside class="card help" id="help"><div style="display:flex;align-items:center"><h2 style="margin:0">Translate</h2><button class="btn quiet helpbtn" id="helpx" style="margin-left:auto;padding:4px 10px">Close</button></div>
      <div class="tr" id="htr" style="margin-top:14px"></div>
      <p class="hint" style="margin-top:14px">Tap a result to copy it. To change a word in the text, double-click the word.</p></aside>
  </div></section>`;
  translator($('#htr'), w => { navigator.clipboard?.writeText(w); toast(`Copied “${w}”`); });
  $('#helpbtn').onclick = () => $('#help').classList.add('on'); $('#helpx').onclick = () => $('#help').classList.remove('on');
  $('#ok').onclick = () => verdict(); $('#skip').onclick = () => verdict('skip');
  $('#prevc').onclick = () => cur > 0 && load(cur - 1); $('#nextc').onclick = () => cur < EX.clips.length - 1 && load(cur + 1);
  load(cur);
}
function rail() {
  $('#rail').innerHTML = EX.clips.map((c, i) => { const v = c.state?.verdict; return `<button class="c ${i === cur ? 'on' : ''}" data-i="${i}">
    <span class="st ${v ? 'done' : touched(c) ? 'half' : ''}">${v ? '✓' : ''}</span><span>Clip ${i + 1}<small>${fmt(c.offset)} · ${v ? {ok: 'Correct', fixed: 'Fixed', skip: 'Skipped'}[v] : 'To review'}</small></span></button>`; }).join('');
  $$('#rail .c').forEach(b => b.onclick = () => load(+b.dataset.i));
  $('#rail .c.on')?.scrollIntoView({block: 'nearest', inline: 'nearest'});
}
function load(i) {
  closeCard(); stopAudio(); flushTime(); cur = i;
  if (i >= EX.clips.length) return finished();
  $('#clipcard').innerHTML = `
    <div class="player"><button class="play" id="play" aria-label="Play clip"><svg id="pi" width="20" height="20" viewBox="0 0 20 20"><path d="M6 3.5v13l11-6.5z" fill="currentColor"/></svg></button>
      <div class="track"><div class="scrub" id="scrub"><div id="ticks"></div><div class="hl" id="hl"></div></div><div class="times"><span id="tcur">0:00</span><span>${fmt(C().dur)}</span></div></div>
      <div class="speed" id="speed"><button data-r=".75">0.75×</button><button data-r="1" class="on">1×</button></div></div>
    <div class="text" id="text"></div>
    <p class="hint">Click a word to hear it. Double-click to correct it, find the right word or comment.</p>
    <div class="keyline"><span><u style="border-bottom:2px dotted var(--sage)"></u>Auto-fixed, check it</span><span><u style="border-bottom:2px solid var(--sand)"></u>Worth a second listen</span><span><u style="border-bottom:2px solid var(--sage-d)"></u>Your change</span><span><span class="dot" style="background:var(--flag)"></span>Your comment</span></div>
    <div class="sect"><h3>Comment on the whole clip</h3><div class="chips" id="clipchips"></div>
      <div class="field" style="margin-top:12px"><input id="clipnote" placeholder="Anything about this clip"><button class="mic" id="clipmic" title="Record a voice note"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button></div>
      <div id="clipvoice"></div></div>
    <div class="sect"><h3>Before and after</h3><div class="cmp"><div><small>myt wrote</small><span id="before"></span></div><div><small>Your version</small><span id="after"></span></div></div></div>`;
  $('#play').onclick = () => { if (audio.paused) playClip(); else stopAudio(); };
  $('#scrub').onpointerdown = e => { const r = e.currentTarget.getBoundingClientRect(); heardJ = null; audio.currentTime = C().offset + Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * C().dur; stopAt = C().offset + C().dur; };
  $$('#speed button').forEach(b => b.onclick = () => { audio.playbackRate = +b.dataset.r; $$('#speed button').forEach(x => x.classList.toggle('on', x === b)); });
  $('#clipchips').innerHTML = CLIP_WHY.map(w => `<button class="chip ${S().why.includes(w) ? 'on' : ''}">${w}</button>`).join('');
  $$('#clipchips .chip').forEach(b => b.onclick = () => { const w = S().why, k = w.indexOf(b.textContent); k < 0 ? w.push(b.textContent) : w.splice(k, 1); b.classList.toggle('on'); save(); });
  $('#clipnote').value = S().note || '';
  $('#clipnote').oninput = e => { S().note = e.target.value; clearTimeout(load.t); load.t = setTimeout(save, 700); };
  $('#clipmic').onclick = () => record($('#clipmic'), null, () => voiceList($('#clipvoice'), C().voice.filter(v => v.word == null)));
  voiceList($('#clipvoice'), C().voice.filter(v => v.word == null));
  $('#clipno').textContent = `Clip ${cur + 1} of ${EX.clips.length}`; $('#prevc').disabled = cur === 0; $('#nextc').disabled = cur === EX.clips.length - 1;
  $('#ok').hidden = $('#skip').hidden = false;
  history.replaceState(null, '', `#/r/${encodeURIComponent(EX.id)}/${cur}`);
  audio.currentTime = C().offset;
  rail(); text();
}
function text() {
  const toks = C().tokens;
  $('#text').innerHTML = toks.map((t, i) => { const e = S().edits[i] || {};
    const cls = e.gone ? 'gone' : mine(t, i) ? 'mine' : t.auto ? 'fix' : t.low ? 'low' : '';
    return `<span class="w ${cls}${flagged(i) ? ' flagged' : ''}" data-j="${i}">${esc(shown_(t, i))}</span>`; }).join(' ');
  $$('#text .w').forEach(el => el.onclick = () => { const j = +el.dataset.j, now = Date.now();  // one tap: hear it; second tap: open its card
    if (lastTap.j === j && now - lastTap.t < 350) { lastTap = {}; openCard(j); } else { lastTap = {j, t: now}; hear(j); } });
  $('#okl').textContent = toks.some((t, i) => mine(t, i)) ? 'Save & next clip' : 'Clip is correct';
  $('#ticks').innerHTML = toks.map((t, i) => `<i class="${flagged(i) || mine(t, i) ? 'flag' : ''}" style="left:${t.s / C().dur * 100}%;height:${8 + ((t.t.length * 7) % 18)}px"></i>`).join('');
  $('#before').innerHTML = toks.map((t, i) => mine(t, i) ? `<span class="was">${esc(t.t)}</span>` : esc(t.t)).join(' ');
  const notes = [];
  $('#after').innerHTML = toks.map((t, i) => { const e = S().edits[i] || {}; if (e.gone) return null;
    let h = mine(t, i) || t.auto ? `<span class="now2">${esc(shown_(t, i))}</span>` : esc(shown_(t, i));
    if (flagged(i)) { h = `<span class="fl">${h}</span>`; notes.push(`<b>${esc(shown_(t, i))}</b>: ${esc([...(e.why || []), ...(e.note ? [e.note] : []), ...wordVoice(i).map(v => `voice: “${v.transcript || '…'}”`)].join(' · '))}`); }
    return h; }).filter(x => x != null).join(' ') + notes.map(n => `<span class="note">${n}</span>`).join('');
}

/* audio: a clip plays between its own start and end; a tapped word plays alone */
function playClip() { const c = C(); if (audio.currentTime < c.offset || audio.currentTime >= c.offset + c.dur - .05) audio.currentTime = c.offset; heardJ = null; stopAt = c.offset + c.dur; audio.play().catch(() => {}); }
function hear(j) { const t = C().tokens[j]; audio.currentTime = C().offset + Math.max(0, t.s - .06); stopAt = C().offset + t.e + .12; heardJ = j; audio.play().catch(() => {}); }
const PLAY = '<path d="M6 3.5v13l11-6.5z" fill="currentColor"/>', PAUSE = '<rect x="5" y="4" width="3.5" height="12" rx="1" fill="currentColor"/><rect x="11.5" y="4" width="3.5" height="12" rx="1" fill="currentColor"/>';
audio.onplay = () => $('#pi') && ($('#pi').innerHTML = PAUSE); audio.onpause = () => $('#pi') && ($('#pi').innerHTML = PLAY);
// backup for the frame loop below, which browsers slow down in background tabs
audio.ontimeupdate = () => { if (stopAt !== null && audio.currentTime >= stopAt) { audio.pause(); stopAt = null; heardJ = null; } };
(function tick() {
  if (EX && $('#text')) {
    const c = C(), t = audio.currentTime - c.offset, live = !audio.paused;
    if (stopAt !== null && audio.currentTime >= stopAt) { audio.pause(); stopAt = null; heardJ = null; }
    $('#hl').style.left = Math.max(0, Math.min(100, t / c.dur * 100)) + '%'; $('#tcur').textContent = fmt(Math.max(0, t));
    $$('#text .w').forEach((el, j) => el.classList.toggle('now', live && (heardJ !== null ? j === heardJ : t >= c.tokens[j].s && t < c.tokens[j].e + .04)));
  }
  requestAnimationFrame(tick);
})();

/* saving: every change is sent at once; time spent goes with it */
function flushTime() { const s = (Date.now() - clipT0) / 1000; clipT0 = Date.now(); return Math.min(s, 600); }
async function save(v) {
  const s = S(); if (v) s.verdict = v;
  try { await api('clip/' + C().clip_id, {method: 'PUT', body: {verdict: v || null, edits: s.edits, why: s.why, note: s.note || '', seconds: flushTime()}}); }
  catch (e) { if (e.message !== 'login') toast('Not saved: ' + e.message); }
}
async function verdict(v) {
  const s = S(); v = v || (C().tokens.some((t, i) => mine(t, i)) ? 'fixed' : 'ok');
  await save(v); toast({ok: 'Marked correct', fixed: 'Fixes saved', skip: 'Skipped for now'}[v] + ` · clip ${cur + 1}`);
  OV = null; load(cur + 1);
}
async function finished() {
  stopAudio(); OV = await api('overview'); pill(OV); rail();
  $('#ok').hidden = $('#skip').hidden = true; $('#clipno').textContent = 'Done'; $('#nextc').disabled = true; $('#prevc').disabled = false;
  const n = nextUp(OV, EX.category) || nextUp(OV);
  $('#clipcard').innerHTML = `<div class="donebox"><span class="st done" style="width:44px;height:44px;margin:0 auto;font-size:1.1rem">✓</span>
    <h1>Recording done</h1><p class="sub">${hm(OV.hours_done)} of ${Math.round(OV.hours_total)} h reviewed.</p>
    <div style="display:flex;gap:10px;justify-content:center;margin-top:22px;flex-wrap:wrap"><a class="btn ghost" href="#/c/${encodeURIComponent(EX.category)}">${nice(EX.category)}</a>${n ? `<a class="btn primary" href="#/r/${encodeURIComponent(n.id)}">Next recording${n.category !== EX.category ? ` · ${nice(n.category)}` : ''} →</a>` : ''}</div></div>`;
}

/* ───── word card: 1 correct, 2 translate, 3 comment ───── */
let cj = null, draft = null;
function openCard(j) {
  const t = C().tokens[j], e = S().edits[j] || {};
  cj = j; draft = {why: [...(e.why || [])], gone: !!e.gone};
  $$('#text .w').forEach(el => el.classList.toggle('sel', +el.dataset.j === j));
  $('#wcword').textContent = t.t; $('#wcwhen').textContent = `myt wrote this · at ${fmt(C().offset + t.s)}`;
  $('#wcin').value = shown_(t, j); $('#wcnote').value = e.note || '';
  cardTr.reset();
  $('#wcchips').innerHTML = WORD_WHY.map(w => `<button class="chip ${draft.why.includes(w) ? 'on' : ''}">${w}</button>`).join('');
  $$('#wcchips .chip').forEach(b => b.onclick = () => { const k = draft.why.indexOf(b.textContent); k < 0 ? draft.why.push(b.textContent) : draft.why.splice(k, 1); b.classList.toggle('on'); });
  $('#wcrm').textContent = draft.gone ? 'Put this word back' : 'Remove this word (not said)';
  voiceList($('#wcvoice'), wordVoice(j));
  const wc = $('#wc');
  if (!phone()) {
    const el = $(`#text .w[data-j="${j}"]`), W = 440, H = Math.min(wc.scrollHeight || 600, innerHeight * .82);
    let r = el.getBoundingClientRect();
    const hb = $('#rvbar').getBoundingClientRect().bottom;  // keep clear of the sticky header
    if (r.bottom + H + 20 > innerHeight && r.top - H - 20 < hb) { scrollBy(0, r.bottom + H + 24 - innerHeight); r = el.getBoundingClientRect(); }
    const left = Math.max(12, Math.min(innerWidth - W - 12, r.left + r.width / 2 - W / 2)), below = r.bottom + H + 20 <= innerHeight;
    wc.style.left = left + 'px'; wc.style.top = (below ? r.bottom + 10 : Math.max(hb + 8, r.top - H - 10)) + scrollY + 'px';
    wc.style.transformOrigin = `${r.left + r.width / 2 - left}px ${below ? '0' : '100%'}`;
  } else { const r = $(`#text .w[data-j="${j}"]`).getBoundingClientRect(); scrollBy({top: r.top - $('#rvbar').getBoundingClientRect().bottom - 12, behavior: 'smooth'}); }
  wc.scrollTop = 0; wc.classList.add('on'); $('#scrim').classList.add('on');
  setTimeout(() => { $('#wcin').focus(); $('#wcin').select(); }, 60);
  hear(j);
}
function closeCard() { $('#wc').classList.remove('on'); $('#scrim').classList.remove('on'); $$('#text .w.sel').forEach(el => el.classList.remove('sel')); cj = null; if (rec?.state === 'recording') rec.stop(); }
function saveCard() {
  const t = C().tokens[cj], v = $('#wcin').value.trim().replace(/\s+/g, ' '), e = {};
  if (draft.gone || !v) e.gone = true; else if (v !== (t.auto ?? t.t)) e.show = v;
  if (draft.why.length) e.why = draft.why;
  if ($('#wcnote').value.trim()) e.note = $('#wcnote').value.trim();
  if (Object.keys(e).length) S().edits[cj] = e; else delete S().edits[cj];
  const said = e.gone ? 'Word removed' : e.show ? 'Fix saved' : (e.why || e.note) ? 'Comment saved' : 'No change';
  closeCard(); text(); save(); toast(said);
}
$('#wcin').onkeydown = $('#wcnote').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); saveCard(); } if (e.key === 'Escape') closeCard(); };
$('#wcsave').onclick = saveCard; $('#wccancel').onclick = $('#wcx').onclick = $('#scrim').onclick = closeCard;
$('#wchear').onclick = () => hear(cj);
$('#wcrm').onclick = () => { draft.gone = !draft.gone; if (draft.gone) saveCard(); else $('#wcrm').textContent = 'Remove this word (not said)'; };
addEventListener('keydown', e => { if (e.key === 'Escape') { closeCard(); $('#help')?.classList.remove('on'); } });

/* translator: your word on the left (its language), the translation on the right (the language you want).
   Dictionary results appear while typing; "Translate" asks Claude. Every word gets a definition, or "Don't know". */
const LN = {mfe: 'Kreol', fr: 'French', en: 'English'};
const fold = s => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
const defHtml = (lang, d) => !d ? '' : `<span class="lg">${LN[lang]}</span>${/^don.?t know/i.test(d) ? '<span class="dk">Don’t know</span>' : esc(d)}`;
function translator(box, use) {
  const sel = v => Object.entries(LN).map(([k, l]) => `<option value="${k}" ${k === v ? 'selected' : ''}>${l}</option>`).join('');
  box.innerHTML = `<div class="seg mode"><button data-m="tr" class="on">Translate</button><button data-m="find">Find</button></div>
    <div class="sides">
      <div class="side"><small class="cap">I write in</small><select class="from" aria-label="I write in">${sel('fr')}</select><textarea class="q" rows="2"></textarea><div class="def sdef"></div></div>
      <button class="swap" title="Swap languages" aria-label="Swap languages">⇄</button>
      <div class="side out"><small class="cap">Into</small><select class="to" aria-label="Into">${sel('mfe')}</select><div class="opts"></div></div></div>
    <div class="go"><button class="btn primary small ask">Translate</button><span class="status"></span></div>`;
  const [q, from, to, out, sdef, st, ask, swap, capTo] = ['.q', '.from', '.to', '.opts', '.sdef', '.status', '.ask', '.swap', '.out .cap'].map(c => box.querySelector(c));
  let local = {source_definition: '', options: []}, ai = null, timer, find = false;
  // Find = search inside the language you write in (misspelled, as it sounds, or a meaning); Translate = into another language
  function setMode(f) {
    find = f; box.classList.toggle('find', f);
    box.querySelectorAll('.mode button').forEach(b => b.classList.toggle('on', (b.dataset.m === 'find') === f));
    capTo.textContent = f ? 'Matches' : 'Into'; ask.textContent = f ? 'Find' : 'Translate';
    q.placeholder = f ? 'Type it as you hear it, or its meaning' : 'Type a word';
    if (f) to.value = from.value; else if (to.value === from.value) to.value = from.value === 'mfe' ? 'fr' : 'mfe';
    instant();
  }
  function render() {
    const seen = new Set(), list = [...(ai?.options || []), ...local.options].filter(x => !seen.has(fold(x.text)) && seen.add(fold(x.text)));
    out.innerHTML = list.map((x, i) => `<button class="opt" data-i="${i}"><b>${esc(x.text)}</b><p class="${/^don.?t know/i.test(x.definition) ? 'dk' : ''}">${defHtml(x.lang, x.definition)}</p>${x.from === 'dictionary' ? '<span class="src">from the dictionary</span>' : ''}</button>`).join('')
      || `<div class="empty-out">${q.value.trim() ? (ai ? 'Nothing found.' : `Press ${find ? 'Find' : 'Translate'}.`) : find ? 'Matching words appear here.' : 'The translation appears here.'}</div>`;
    out.querySelectorAll('.opt').forEach(b => b.onclick = () => { const x = list[+b.dataset.i]; use(x.text);
      if (ai?.id && x.from !== 'dictionary') api('ask/choose', {method: 'POST', body: {id: ai.id, text: x.text}}).catch(() => {}); });
    const d = ai?.source_definition || local.source_definition;
    sdef.innerHTML = q.value.trim() ? defHtml(from.value, d) : '';
  }
  function instant() {
    clearTimeout(timer); ai = null; st.textContent = ''; st.className = 'status';
    const v = q.value.trim(); if (!v) { local = {source_definition: '', options: []}; return render(); }
    timer = setTimeout(async () => { local = await api(`translate?q=${encodeURIComponent(v)}&src=${from.value}&lang=${to.value}`).catch(() => local); render(); }, 150);
  }
  async function translate() {
    const v = q.value.trim(); if (!v) return q.focus();
    st.className = 'status'; st.textContent = find ? 'Searching…' : 'Translating…'; ask.disabled = true;
    try {
      const ctx = EX && $('#text') ? C().tokens.map((t, i) => shown_(t, i)).join(' ') : '';
      ai = await api('ask', {method: 'POST', body: {q: v, src: from.value, lang: to.value, context: ctx, clip_id: EX ? C().clip_id : ''}});
      st.textContent = `Claude: $${ai.spent.toFixed(2)} of $${ai.budget.toFixed(0)} used`;
    } catch (e) { st.className = 'status err'; st.textContent = e.message; }
    ask.disabled = false; render();
  }
  const fix = changed => { if (find) to.value = from.value; else if (from.value === to.value) (changed === from ? to : from).value = Object.keys(LN).find(k => k !== from.value); instant(); };
  box.querySelectorAll('.mode button').forEach(b => b.onclick = () => setMode(b.dataset.m === 'find'));
  from.onchange = () => fix(from); to.onchange = () => fix(to);
  swap.onclick = () => { const first = out.querySelector('.opt b')?.textContent; [from.value, to.value] = [to.value, from.value]; if (first) q.value = first; instant(); };
  q.oninput = instant;
  q.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); translate(); } if (e.key === 'Escape') closeCard(); };
  ask.onclick = translate;
  setMode(false);
  return {reset() { q.value = ''; local = {source_definition: '', options: []}; ai = null; st.textContent = ''; render(); }};
}
const cardTr = translator($('#wctr'), w => { $('#wcin').value = w; $('#wcin').focus(); toast(`“${w}” put in the correct word box`); });

/* voice notes: recorded in the browser, stored and transcribed on the server (myt, English/French) */
let rec = null;
async function record(btn, word, after) {
  if (rec?.state === 'recording') { rec.stop(); return; }
  let st;
  try { st = await navigator.mediaDevices.getUserMedia({audio: true}); }
  catch (e) { toast('Microphone not available: allow it in the browser'); return; }
  const chunks = [], clip = C();
  rec = new MediaRecorder(st);
  rec.ondataavailable = e => chunks.push(e.data);
  rec.onstop = async () => {
    st.getTracks().forEach(t => t.stop()); btn.classList.remove('rec'); btn.classList.add('busy');
    const fd = new FormData(); fd.append('file', new Blob(chunks, {type: rec.mimeType || 'audio/webm'}), 'note.webm'); fd.append('clip_id', clip.clip_id);
    if (word != null) fd.append('word', word);
    try { const v = await api('voice', {method: 'POST', body: fd}); clip.voice.push(v); toast(v.transcript ? 'Voice note saved and transcribed' : 'Voice note saved'); after(); if (EX && C() === clip && !$('#wc').classList.contains('on')) text(); }
    catch (e) { toast('Voice note not saved: ' + e.message); }
    btn.classList.remove('busy');
  };
  rec.start(); btn.classList.add('rec'); toast('Recording… tap the mic again to stop');
}
function voiceList(el, arr) { el.innerHTML = arr.map(v => `<div class="vnote"><audio controls preload="none" src="api/voice/${v.id}"></audio><span>${v.transcript ? `<em>“${esc(v.transcript)}”</em>` : 'No transcript'}</span></div>`).join(''); }
$('#wcmic').onclick = () => record($('#wcmic'), cj, () => voiceList($('#wcvoice'), wordVoice(cj)));

/* ───── learning ───── */
async function learning() {
  const [L, ov] = await Promise.all([api('learning'), OV ? OV : api('overview')]); OV = ov; pill(ov);
  const maxR = Math.max(1, ...L.reasons.map(r => r[1]));
  $('#main').innerHTML = `<section class="screen"><h1>What Claude is learning</h1><p class="sub" style="margin-top:6px">Your fixes become rules. The rules fix the other 90 hours.</p>
  <div class="card" style="margin-top:20px"><div class="flow">
    <div class="s"><b>1 · You fix</b><span>8 h of clips, word by word</span></div><div class="arr">→</div>
    <div class="s"><b>2 · Claude finds patterns</b><span>Dictionary, rules and examples</span></div><div class="arr">→</div>
    <div class="s"><b>3 · The exam</b><span>2 h Claude never sees: must beat myt</span></div><div class="arr">→</div>
    <div class="s"><b>4 · The 90 hours</b><span>Fixed in batches; doubtful clips come back to you</span></div></div></div>
  <div class="grid two" style="margin-top:20px">
    <div class="card"><h2>Why words were fixed</h2>${L.reasons.length ? L.reasons.map(([k, n]) => `<div class="rowbar"><span>${esc(k)}</span><div class="bar"><i style="width:${n / maxR * 100}%"></i></div><span class="n">${n}</span></div>`).join('') : '<p class="empty">Reasons you pick in the word card appear here.</p>'}
      <div style="height:16px"></div><h2>Most common fixes · ${L.fixes} so far</h2>
      ${L.top.length ? `<table><tr><th>myt wrote</th><th>you wrote</th><th style="text-align:right">times</th></tr>${L.top.map(([a, b, n]) => `<tr><td class="from">${esc(a)}</td><td class="to">${esc(b)}</td><td class="n">${n}</td></tr>`).join('')}</table>` : '<p class="empty">Your fixes appear here as you review.</p>'}</div>
    <div class="grid">
      <div class="card"><h2>Rules Claude proposes</h2>${L.rules.length ? L.rules.map(r => `<div class="prop"><div><p>Write <b class="to">${esc(r.to)}</b> instead of <span class="from">${esc(r.from)}</span></p><small>You made this fix ${r.seen}×</small></div>
        <div class="yn" data-k="${esc(r.key)}"><button class="y ${r.decision === 'yes' ? 'on' : ''}" title="Yes, apply it">✓</button><button class="n ${r.decision === 'no' ? 'on' : ''}" title="No">✕</button></div></div>`).join('') : '<p class="empty">A rule is proposed once you make the same fix 3 times.</p>'}</div>
      <div class="card"><h2>The exam</h2><p class="sub" style="font-size:.88rem">After your first hour, Claude corrects exam clips without seeing your answers. Here you'll see the share of words wrong: myt alone vs Claude with your rules.</p></div>
      <div class="card"><h2>Claude searches</h2><div class="rowbar"><span>Budget used</span><div class="bar"><i style="width:${L.spent / L.budget * 100}%"></i></div><span class="n">$${L.spent.toFixed(2)} / ${L.budget.toFixed(0)}</span></div>
        <p class="sub" style="font-size:.86rem">${L.lookups} searches · ${L.chosen} suggestions used</p></div>
    </div></div></section>`;
  $$('.yn').forEach(g => g.querySelectorAll('button').forEach(b => b.onclick = async () => {
    const d = b.classList.contains('y') ? 'yes' : 'no'; await api('rules', {method: 'POST', body: {key: g.dataset.k, decision: d}});
    g.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); toast(d === 'yes' ? 'Rule approved' : 'Rule rejected'); }));
}

/* ───── start ───── */
async function start() {
  const me = await api('me');
  if (!me.ok) return login();
  $('#top').hidden = false; route();
}
start();
