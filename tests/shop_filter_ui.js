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
  const documentHandlers = {};
  function makeSearch(value) {
    const input = {value, focused: false, focus(options) { assert.equal(options.preventScroll, true); this.focused = true; }, matches: selector => selector === '#search'};
    const cross = {hidden: !value, closest: selector => selector === '[data-clear-search]' ? cross : searchForm};
    const searchForm = {querySelector: selector => selector === '[data-clear-search]' ? cross : input};
    input.closest = () => searchForm;
    return {input, cross};
  }
  let search = makeSearch('Sea');
  function makeResults(url, searchState) {
    return {url, searchState, setAttribute() {}, removeAttribute() {}, replaceWith(next) { results = next; search = next.searchState; }, querySelector(selector) { return selector === 'input[name="q"]' ? this.searchState.input : this.searchState.cross; }};
  }
  let results = makeResults('', search);
  const location = new URL('https://example.test/shop#collection');
  location.reload = () => { throw new Error('Unexpected reload'); };
  const pushes = [], urls = [];
  let deferred, failNext = false;
  const document = {
    querySelector(selector) { return selector === '.category-form' ? form : selector === '.shop-results' ? results : selector.startsWith('.shop-search') ? search.input : selector === '[data-clear-search]' ? search.cross : null; },
    addEventListener: (name, handler) => { documentHandlers[name] = handler; },
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
      const nextResults = makeResults(text, makeSearch(q || ''));
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

  // A failed clear restores the applied query instead of presenting stale results as cleared.
  failNext = true;
  documentHandlers.click({target: search.cross, preventDefault() {}});
  await tick();
  assert.equal(search.input.value, 'Sea');
  assert.equal(search.cross.hidden, false);
  assert.equal(error.hidden, false);
  assert.equal(error.textContent, 'Could not clear the search. Please try again.');

  // Clearing the search is immediate, keeps the categories, and updates the results in place.
  documentHandlers.click({target: search.cross, preventDefault() {}});
  await tick();
  assert.equal(new URL(results.url).searchParams.get('q'), null);
  assert.equal(new URL(results.url).searchParams.getAll('category[]').length, 3);
  assert.equal(search.input.value, '');
  assert.equal(search.cross.hidden, true);
  assert.equal(search.input.focused, true);
  search.input.value = 'new words';
  documentHandlers.input({target: search.input});
  assert.equal(search.cross.hidden, false);
  documentHandlers.click({target: search.cross, preventDefault() {}});
  await tick();
  assert.equal(search.input.value, '');
  assert.equal(search.cross.hidden, true);

  // Keep text entered while a request is pending rather than replacing it.
  deferred = true;
  boxes[0].checked = false;
  change();
  const resolveTyping = deferred;
  deferred = null;
  search.input.value = 'typed while loading';
  documentHandlers.input({target: search.input});
  resolveTyping();
  await tick();
  assert.equal(search.input.value, 'typed while loading');
  assert.equal(search.cross.hidden, false);

  handlers['clear-click']({preventDefault() {}});
  await tick();
  assert.equal(boxes.filter(box => box.checked).length, 0);
  assert.equal(clear.hidden, true);
  assert.equal(new URL(results.url).searchParams.get('q'), 'typed while loading');

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
  console.log('Shop filters and search clear update in place, retain state, and handle races and history.');
})().catch(err => { console.error(err); process.exitCode = 1; });
