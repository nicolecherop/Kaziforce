const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/js/skills.js'), 'utf8');

function setup(fetch) {
  let listener;
  let timer;
  const input = {value: '', matches: () => true};
  const list = {dataset: {url: '/skills/search/'}, children: [], replaceChildren(...items) { this.children = items; }};
  const status = {textContent: ''};
  const document = {activeElement: input, querySelector: selector => selector.includes('suggestions') ? list : status, addEventListener(type, fn) { listener = fn; }, createElement: () => ({})};
  vm.runInNewContext(source, {document, window: {location: {origin: 'http://localhost'}}, URL, AbortController, fetch, setTimeout(fn) {timer = fn;}, clearTimeout() {timer = null;}});
  return {input, list, status, enter(value) {input.value = value; listener({target: input});}, run() {return timer?.();}};
}

test('requests local suggestions and inserts labels as text values', async () => {
  let requestUrl;
  const ui = setup(async url => {requestUrl = url; return {ok: true, json: async () => ({suggestions: [{label: '<script>literal</script>', matched_label: 'Python'}]})};});
  ui.enter('Py');
  await ui.run();
  assert.equal(requestUrl.origin, 'http://localhost');
  assert.equal(requestUrl.pathname, '/skills/search/');
  assert.equal(ui.list.children[0].value, '<script>literal</script>');
  assert.match(ui.status.textContent, /1 skill suggestions/);
});

test('out-of-order responses cannot replace newer suggestions', async () => {
  const pending = [];
  const ui = setup(() => new Promise(resolve => pending.push(resolve)));
  ui.enter('Py'); const older = ui.run();
  ui.enter('SQ'); const newer = ui.run();
  pending[1]({ok: true, json: async () => ({suggestions: [{label: 'SQL', matched_label: 'SQL'}]})});
  await newer;
  pending[0]({ok: true, json: async () => ({suggestions: [{label: 'Python', matched_label: 'Python'}]})});
  await older;
  assert.equal(ui.list.children[0].value, 'SQL');
});

test('network failures preserve typed skills and explain the fallback', async () => {
  const ui = setup(async () => {throw new Error('offline');});
  ui.enter('My specialist skill');
  await ui.run();
  assert.equal(ui.input.value, 'My specialist skill');
  assert.match(ui.status.textContent, /still enter and save/);
});

test('short input clears suggestions and makes no request', async () => {
  let requests = 0;
  const ui = setup(async () => {requests++;});
  ui.list.children = [{value: 'Old result'}];
  ui.enter('P');
  await ui.run();
  assert.equal(requests, 0);
  assert.equal(ui.list.children.length, 0);
});
