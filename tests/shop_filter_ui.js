// Run with `node tests/shop_filter_ui.js`. Exercises filtering without a browser dependency.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

(async () => {
  const boxes = ['Fiction', 'Poetry', 'Drama', 'Literary Studies'].map(value => ({value, checked: false}));
  const handlers = {}, windowHandlers = {}, error = {hidden: true, textContent: ''};
  const clear = {hidden: true, href: '/shop#collection', addEventListener: (name, fn) => { handlers['clear-' + name] = fn; }, setAttribute: (_, value) => { clear.href = value; }};
  let queryInput = null;
  const form = {
    action: 'https://example.test/shop#collection',
    addEventListener: (name, fn) => { handlers[name] = fn; },
    querySelectorAll: () => boxes,
    querySelector: selector => selector === '.category-clear' ? clear : selector === '[data-filter-error]' ? error : queryInput,
    appendChild: input => { queryInput = input; input.remove = () => { queryInput = null; }; }
  };
  let results = {setAttribute() {}, removeAttribute() {}, replaceWith(next) { results = next; }};
  const search = {value: 'Sea'};
  const location = new URL('https://example.test/shop#collection');
  location.reload = () => { throw new Error('Unexpected reload'); };
  const pushes = [], urls = [];
  let deferred, failNext = false;
  const document = {
    querySelector(selector) { return selector === '.category-form' ? form : selector === '.shop-results' ? results : selector.startsWith('.shop-search') ? search : null; },
    createElement() { return {}; }
  };
  class FakeFormData {
    *[Symbol.iterator]() { for (const box of boxes) if (box.checked) yield ['category[]', box.value]; if (queryInput) yield ['q', queryInput.value]; }
  }
  class FakeDOMParser {
    parseFromString(text) {
      const url = new URL(text);
      const selected = url.searchParams.getAll('category[]');
      const q = url.searchParams.get('q');
      const nextForm = {
        querySelectorAll: () => boxes.map(box => ({value: box.value, checked: selected.includes(box.value)})),
        querySelector(selector) {
          if (selector === '.category-clear') return {hidden: selected.length === 0, getAttribute: () => '/shop' + (q ? '?q=' + q : '') + '#collection'};
          return q ? {value: q} : null;
        }
      };
      const nextResults = {setAttribute() {}, removeAttribute() {}, replaceWith(next) { results = next; }, url: text};
      return {querySelector: selector => selector === '.shop-results' ? nextResults : nextForm};
    }
  }
  const context = {
    document, location, URL, URLSearchParams, AbortController, FormData: FakeFormData, DOMParser: FakeDOMParser,
    history: {pushState(_, __, path) { pushes.push(path); location.href = new URL(path, location.href); }},
    window: {addEventListener: (name, fn) => { windowHandlers[name] = fn; }},
    fetch: async url => {
      urls.push(url.href);
      if (failNext) { failNext = false; throw new Error('Offline'); }
      if (deferred === true) return new Promise(resolve => { deferred = () => resolve({ok: true, text: async () => url.href}); });
      return {ok: true, text: async () => url.href};
    }
  };
  vm.runInNewContext(fs.readFileSync('assets/shop-filter.js', 'utf8'), context);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const change = () => handlers.change({target: {matches: () => true}});

  boxes[0].checked = true;
  change();
  await tick();
  assert.equal(new URL(urls[0]).searchParams.get('category[]'), 'Fiction');
  assert.equal(new URL(urls[0]).searchParams.get('q'), 'Sea');
  assert.equal(clear.hidden, false);
  assert.equal(boxes[0].checked, true);
  assert.equal(pushes.length, 1);

  // A slower earlier request must never overwrite the latest selection.
  deferred = true;
  boxes[2].checked = true;
  change();
  const resolveOld = deferred;
  deferred = null;
  boxes[1].checked = true;
  change();
  await tick();
  resolveOld();
  await tick();
  assert.deepEqual(boxes.filter(box => box.checked).map(box => box.value), ['Fiction', 'Poetry', 'Drama']);
  assert.equal(new URL(results.url).searchParams.getAll('category[]').length, 3);

  handlers['clear-click']({preventDefault() {}});
  await tick();
  assert.equal(boxes.filter(box => box.checked).length, 0);
  assert.equal(clear.hidden, true);
  assert.equal(new URL(results.url).searchParams.get('q'), 'Sea');

  // A failed request restores the last applied checkboxes, without navigating.
  failNext = true;
  boxes[2].checked = true;
  change();
  await tick();
  assert.equal(boxes[2].checked, false);
  assert.equal(error.hidden, false);

  location.href = 'https://example.test/shop?category%5B%5D=Fiction&q=Sea#collection';
  windowHandlers.popstate();
  await tick();
  assert.equal(boxes[0].checked, true);
  assert.equal(boxes[2].checked, false);
  assert.equal(error.hidden, true);
  console.log('Shop filters update in place, retain state, and handle races and history.');
})().catch(err => { console.error(err); process.exitCode = 1; });
