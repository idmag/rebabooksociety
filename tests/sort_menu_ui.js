// Run with jsdom installed: NODE_PATH=/path/to/node_modules node tests/sort_menu_ui.js
const assert = require('assert');
const fs = require('fs');
const {JSDOM} = require('jsdom');

const options = [['recommended', 'Recommended'], ['price-asc', 'Price: Low to High'], ['title-desc', 'Title: Z to A']];
function page(url) {
  const query = new URL(url).searchParams;
  const category = query.get('category[]') === 'Fiction';
  const sort = query.get('sort') || 'recommended';
  const q = query.get('q') || '';
  return `<form class="category-form" action="/shop"><input type="checkbox" name="category[]" value="Fiction" ${category ? 'checked' : ''}>
    ${q ? `<input name="q" value="${q}">` : ''}${sort !== 'recommended' ? `<input name="sort" value="${sort}">` : ''}<a class="category-clear" href="/shop" ${category ? '' : 'hidden'}>Clear</a><p data-filter-error hidden></p></form>
    <div class="shop-results"><div class="shop-search"><form class="sort-form"><label for="shop-sort">Sort By</label><span class="sort-select-wrap"><select id="shop-sort" name="sort" data-sort-select>${options.map(([value, label]) => `<option value="${value}" ${value === sort ? 'selected' : ''}>${label}</option>`).join('')}</select><svg class="sort-chevron"></svg></span></form>
    <form class="search-form"><input id="search" name="q" value="${q}"><a data-clear-search href="/shop" ${q ? '' : 'hidden'}>Clear</a></form></div></div>`;
}
(async () => {
  const dom = new JSDOM(page('https://example.test/shop?q=Sea'), {url:'https://example.test/shop?q=Sea', runScripts:'outside-only'});
  const {window} = dom, {document} = window;
  let fail = false, requested;
  window.fetch = async url => {
    requested = url.toString();
    if (fail) { fail = false; throw new Error('offline'); }
    return {ok:true, text:async () => page(requested)};
  };
  window.eval(fs.readFileSync('assets/shop-filter.js', 'utf8'));
  window.eval(fs.readFileSync('assets/sort-menu.js', 'utf8'));
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const trigger = () => document.querySelector('[data-sort-trigger]');
  const menu = () => document.querySelector('[role=listbox]');
  const option = i => menu().querySelectorAll('[role=option]')[i];
  const key = (element, key) => element.dispatchEvent(new window.KeyboardEvent('keydown', {key, bubbles:true}));
  assert.equal(document.querySelector('select').hidden, true);
  assert.equal(trigger().textContent, 'Recommended');
  trigger().click();
  assert.equal(trigger().getAttribute('aria-expanded'), 'true');
  assert.equal(document.activeElement, option(0));
  key(option(0), 'End');
  assert.equal(document.activeElement, option(2));
  key(option(2), 'Home');
  key(option(0), 'ArrowDown');
  assert.equal(document.activeElement, option(1));
  option(1).click();
  await tick();
  assert.equal(new URL(requested).searchParams.get('sort'), 'price-asc');
  assert.equal(new URL(requested).searchParams.get('q'), 'Sea');
  assert.equal(trigger().textContent, 'Price: Low to High');
  assert.equal(document.activeElement, trigger());
  assert.equal(option(1).getAttribute('aria-selected'), 'true');
  assert.equal(menu().hidden, true);
  // A failed update restores the visible selection and keeps the control usable.
  fail = true;
  trigger().click(); option(2).click(); await tick();
  assert.equal(trigger().textContent, 'Price: Low to High');
  assert.equal(document.querySelector('select').value, 'price-asc');
  assert.equal(document.querySelector('[data-filter-error]').hidden, false);
  // Category replacement reconstructs the menu with the applied sort and search.
  const checkbox = document.querySelector('[name="category[]"]');
  checkbox.checked = true;
  checkbox.dispatchEvent(new window.Event('change', {bubbles:true}));
  await tick();
  assert.equal(new URL(requested).searchParams.get('category[]'), 'Fiction');
  assert.equal(new URL(requested).searchParams.get('sort'), 'price-asc');
  assert.equal(new URL(requested).searchParams.get('q'), 'Sea');
  key(trigger(), 'ArrowDown');
  assert.equal(menu().hidden, false);
  key(document.activeElement, 'Escape');
  assert.equal(menu().hidden, true);
  assert.equal(document.activeElement, trigger());
  trigger().click();
  document.querySelector('#search').focus();
  assert.equal(menu().hidden, true);
  console.log('Custom sort menu supports keyboard, focus, errors and dynamic filtering.');
  dom.window.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
