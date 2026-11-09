// Execute the exact generated script with a minimal DOM, using Node built-ins only.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');

function element(attrs = {}) {
  const classes = new Set();
  const listeners = {};
  return {
    attributes: {...attrs}, hidden: false, disabled: false, value: '', textContent: '', children: [],
    classList: {
      toggle(c, on) {if (on) classes.add(c); else classes.delete(c);},
      contains(c) {return classes.has(c);}, remove(c) {classes.delete(c);}
    },
    getAttribute(k) {return this.attributes[k] ?? null;},
    setAttribute(k,v) {this.attributes[k] = v;},
    removeAttribute(k) {delete this.attributes[k];},
    addEventListener(event, handler) {(listeners[event] ||= []).push(handler);},
    fire(event, target = this) {for (const handler of listeners[event] || []) handler({target});},
    appendChild(child) {
      this.children = this.children.filter(c => c !== child);
      this.children.push(child);
      return child;
    },
    closest(selector) {
      const key = {'.nav-row':'data-cat', '.tag':'data-tag', '.page-number':'data-page'}[selector];
      return key && this.attributes[key] !== undefined ? this : null;
    }
  };
}

function fixture() {
  const entries = Array.from({length:13}, (_, i) => ({
    category: i % 2 ? 'hermes' : 'shared', slug: `site-${i}`, title: `Site ${i}`,
    path: `/shared/site-${i}/`, href: `shared/site-${i}/index.html`,
    description: 'Reference guide', tags: i % 2 ? ['guide'] : ['reference'],
    pinned: i === 0, ingested_date: '2026-08-24', ingested_sort: '2026-08-24T00:00:00+00:00'
  }));
  entries[0].ingested_date = entries[0].ingested_sort = '';
  entries[11].ingested_date = entries[12].ingested_date = '2026-09-10';
  entries[11].ingested_sort = '2026-09-10T23:00:00+00:00';
  entries[12].ingested_sort = '2026-09-10T23:30:00+00:00';
  return execFileSync(process.env.PYTHON || 'python', ['-c',
    'import json,sys; import generate_index as g; print(g.build_html(json.loads(sys.argv[1])))',
    JSON.stringify(entries)], {cwd:root, encoding:'utf8'});
}

// Minimal window: a location whose hash follows history.replaceState.
function fakeWindow(hash = '') {
  const listeners = {};
  const win = {
    location: {hash, pathname: '/', search: ''},
    history: {replaceState(_state, _title, url) {
      win.location.hash = url.includes('#') ? url.slice(url.indexOf('#')) : '';
    }},
    addEventListener(event, handler) {(listeners[event] ||= []).push(handler);},
    go(next) {win.location.hash = next; for (const handler of listeners.hashchange || []) handler();}
  };
  return win;
}

function mount(html, win) {
  const data = JSON.parse(html.match(/const SITES = (.*?);\s*\n/)[1]);
  const attrs = text => Object.fromEntries([...text.matchAll(/([\w-]+)="([^"]*)"/g)].map(m=>[m[1],m[2]]));
  const ids = Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],element()]));
  const nav = [...html.matchAll(/<button[^>]*data-cat="[^"]+"[^>]*>/g)].map(m=>element(attrs(m[0])));
  const tags = [...html.matchAll(/<button[^>]*data-tag="[^"]+"[^>]*>/g)].map(m=>element(attrs(m[0])));
  const pages = [...html.matchAll(/<button[^>]*data-page="[^"]+"[^>]*>/g)].map(m=>element(attrs(m[0])));
  const rows = [...html.matchAll(/<a class="row"[^>]*>/g)].map(m=>element(attrs(m[0])));
  ids.rows.children = [...rows];
  assert.deepEqual(nav.slice(0,3).map(n=>n.getAttribute('data-cat')), ['all','recent','pinned']);
  assert.match(html, /Date ingested/);
  const document = {
    getElementById: id=>ids[id] || null,
    querySelectorAll: selector=>({'#rows .row':rows, '#nav .nav-row':nav,
      '#tags .tag':tags, '#page-buttons .page-number':pages}[selector] || [])
  };
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],
    win ? {document, window: win} : {document});
  const shown = ()=>ids.rows.children.filter(r=>!r.hidden).map(r=>data[Number(r.getAttribute('data-i'))]);
  const select = cat=>ids.nav.fire('click', nav.find(n=>n.getAttribute('data-cat')===cat));
  const reset = ()=>ids.clear.fire('click');
  const all = [...data];
  const chronological = [...data].sort((a,b)=>
    a.ingested_sort === b.ingested_sort ? (a.path < b.path ? -1 : a.path > b.path ? 1 : 0)
      : a.ingested_sort > b.ingested_sort ? -1 : 1);
  return {data, ids, nav, tags, pages, shown, select, reset, all, chronological};
}

function check(html, label) {
  const {data, ids, nav, tags, pages, shown, select, reset, all, chronological} = mount(html);
  assert.deepEqual(shown(), all.slice(0,10));
  assert.equal(ids['recent-columns'].hidden, true);
  select('recent');
  assert.equal(ids.h1.textContent, 'Recent Sites');
  assert.equal(ids['recent-columns'].hidden, false);
  assert.equal(ids.rows.classList.contains('recent'), true);
  let visited = [];
  for (const p of pages) {
    ids['page-buttons'].fire('click', p);
    visited.push(...shown());
  }
  assert.deepEqual(visited, chronological);
  assert.equal(new Set(visited.map(s=>s.path)).size, data.length);
  assert.equal(ids.next.disabled, true);
  ids.previous.fire('click');
  const expectedPrevious = Math.max(0, pages.length-2)*10;
  assert.deepEqual(shown(), chronological.slice(expectedPrevious, expectedPrevious+10));
  console.log(`PASS ${label}: Recent nav placement, timestamp order across pages, DOM order, date column, no pin priority`);
  if (tags.length) {
    reset();select('recent');
    const tag = tags[0].getAttribute('data-tag');
    ids.tags.fire('click', tags[0]);
    assert.deepEqual(shown(), chronological.filter(s=>s.tags.includes(tag)).slice(0,10));
  }
  reset();select('recent');
  if (data.length) {
    const target = chronological[0];
    ids.q.value = target.title.toUpperCase();ids.q.fire('input');
    assert.ok(shown().some(s=>s.path===target.path));
  }
  ids.q.value = 'zzzz-no-matching-site';ids.q.fire('input');
  assert.equal(shown().length,0);assert.equal(ids.empty.hidden,false);assert.equal(ids.pager.hidden,true);
  reset();assert.deepEqual(shown(), all.slice(0,10));assert.equal(ids['recent-columns'].hidden,true);
  assert.equal(ids.rows.classList.contains('recent'),false);
  for (const button of nav.filter(n=>!['recent','all'].includes(n.getAttribute('data-cat')))) {
    reset();select(button.getAttribute('data-cat'));
    const cat=button.getAttribute('data-cat');
    assert.deepEqual(shown(), all.filter(s=>cat==='pinned'?s.pinned:s.category===cat).slice(0,10));
  }
  console.log(`PASS ${label}: Recent search/tag filters, empty state, reset, original categories and pins`);
}
function checkHash(html) {
  // A linked view loads as given.
  let win = fakeWindow('#cat=recent&page=2');
  let m = mount(html, win);
  assert.equal(m.ids.h1.textContent, 'Recent Sites');
  assert.deepEqual(m.shown(), m.chronological.slice(10,20));
  // Every transition is mirrored; defaults leave no hash.
  m.select('hermes');
  assert.equal(win.location.hash, '#cat=hermes');
  m.ids.tags.fire('click', m.tags.find(t=>t.getAttribute('data-tag')==='guide'));
  m.ids.q.value = 'site 1';m.ids.q.fire('input');
  assert.equal(win.location.hash, '#cat=hermes&tag=guide&q=site%201');
  const filtered = m.shown();
  m.reset();
  assert.equal(win.location.hash, '');
  // The hash it wrote restores the same view, including the search box.
  win = fakeWindow('#cat=hermes&tag=guide&q=site%201');
  m = mount(html, win);
  assert.deepEqual(m.shown(), filtered);
  assert.equal(m.ids.q.value, 'site 1');
  // Editing the hash in place re-renders.
  win.go('#cat=pinned');
  assert.deepEqual(m.shown(), m.all.filter(s=>s.pinned));
  // Unknown values fall back to defaults; an oversized page clamps to the last.
  win = fakeWindow('#cat=nope&tag=nope&page=99&junk&q=%E0');
  m = mount(html, win);
  assert.equal(m.ids.h1.textContent, 'All Sites');
  assert.deepEqual(m.shown(), m.all.slice(10));
  assert.equal(win.location.hash, '#page=2');
  console.log('PASS fixture: URL hash loads, mirrors, restores, and rejects unknown values');
}
check(fixture(), 'fixture (ties, unknown, same-day batches)');
checkHash(fixture());
check(execFileSync(process.env.PYTHON || 'python', ['-c',
  'import generate_index as g; print(g.build_html([]))'], {cwd:root, encoding:'utf8'}), 'empty index');
if (process.argv[2]) check(fs.readFileSync(path.resolve(process.argv[2]), 'utf8'), 'repository');
console.log('ALL INDEX BEHAVIOR CHECKS PASS');
