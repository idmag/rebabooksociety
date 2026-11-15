// Run with jsdom installed: NODE_PATH=/path/to/node_modules node tests/cart_drawer_ui.js
const assert = require('assert');
const fs = require('fs');
const {JSDOM} = require('jsdom');

(async () => {
  const dom = new JSDOM(`<!doctype html><body>
  <a data-cart-drawer-toggle href="/cart">Bag <span data-cart-badge hidden>0</span></a>
  <dialog data-cart-drawer id="cart-drawer" aria-labelledby="cart-drawer-title">
    <h2 id="cart-drawer-title">Your cart</h2><button data-drawer-close>Close</button>
    <div data-drawer-body aria-live="polite"></div><a href="/cart">View Cart</a>
    <button data-drawer-close>Continue Shopping</button>
  </dialog>`, {url:'https://example.test/shop?category=Drama', runScripts:'outside-only'});
  const {window} = dom, {document} = window;
  const drawer = document.querySelector('dialog'), toggle = document.querySelector('[data-cart-drawer-toggle]');
  const body = document.querySelector('[data-drawer-body]'), badge = document.querySelector('[data-cart-badge]');
  let desktop = true, fail = false, lastUrl, fetchCount=0, wait;
  window.matchMedia = () => ({get matches() { return desktop; }});
  drawer.showModal = () => { drawer.setAttribute('open', ''); };
  drawer.close = () => { drawer.removeAttribute('open'); drawer.dispatchEvent(new window.Event('close')); };
  window.fetch = async url => {
    lastUrl = url; fetchCount++;
    if (wait) return new Promise(resolve => { wait = resolve; });
    if (fail) { fail = false; throw new Error('Offline'); }
    return {ok:true, headers:{get:()=> 'text/html; charset=utf-8'}, text:async()=>'<div data-drawer-preview data-count="2">Two books</div>'};
  };
  window.eval(fs.readFileSync('assets/cart-drawer.js', 'utf8'));
  const tick = () => new Promise(resolve => setImmediate(resolve));
  let preventedByDrawer;
  toggle.addEventListener('click', e => { preventedByDrawer = e.defaultPrevented; e.preventDefault(); });
  function click(options={}) { toggle.dispatchEvent(new window.MouseEvent('click', {bubbles:true,cancelable:true,button:0,...options})); }
  assert.equal(toggle.getAttribute('aria-haspopup'),'dialog');
  assert.equal(toggle.getAttribute('aria-expanded'),'false');
  click(); await tick();
  assert(preventedByDrawer);
  assert(drawer.open);
  assert.equal(toggle.getAttribute('aria-expanded'),'true');
  assert(document.body.classList.contains('cart-drawer-open'));
  assert.equal(document.activeElement, drawer.querySelector('[data-drawer-close]'));
  assert.equal(lastUrl.pathname,'/cart');
  assert.equal(lastUrl.searchParams.get('preview'),'1');
  assert.equal(body.textContent.trim(),'Two books');
  assert.equal(badge.textContent,'2');
  assert.equal(badge.hidden,false);
  assert(drawer.querySelector('a[href="/cart"]'));
  document.dispatchEvent(new window.Event('cart:updated')); await tick();
  assert.equal(fetchCount,2);
  drawer.querySelector('[data-drawer-close]').click();
  assert(!drawer.open);
  assert.equal(toggle.getAttribute('aria-expanded'),'false');
  assert(!document.body.classList.contains('cart-drawer-open'));
  assert.equal(document.activeElement,toggle);
  // Modifier clicks and mobile clicks retain their normal link behavior.
  click({ctrlKey:true});
  assert.equal(preventedByDrawer,false);
  assert(!drawer.open);
  desktop=false; window.dispatchEvent(new window.Event('resize'));
  assert.equal(toggle.hasAttribute('aria-haspopup'),false);
  click();
  assert.equal(preventedByDrawer,false);
  assert(!drawer.open);
  desktop=true; window.dispatchEvent(new window.Event('resize'));
  fail=true; click(); await tick();
  assert(body.textContent.includes('couldn’t load'));
  assert(drawer.querySelector('a[href="/cart"]'));
  body.querySelector('[data-drawer-retry]').click(); await tick();
  assert.equal(body.textContent.trim(),'Two books');
  desktop=false; window.dispatchEvent(new window.Event('resize'));
  assert(!drawer.open);
  assert(!document.body.classList.contains('cart-drawer-open'));
  // A response from before the drawer was closed must not overwrite a later preview.
  desktop=true; window.dispatchEvent(new window.Event('resize'));
  wait=true; click(); await tick();
  const resolveOld=wait; drawer.close(); wait=false;
  click(); await tick();
  resolveOld({ok:true,headers:{get:()=> 'text/html'},text:async()=>'<div data-drawer-preview data-count="9">Old</div>'});
  await tick();
  assert.equal(body.textContent.trim(),'Two books');
  assert.equal(badge.textContent,'2');
  drawer.close(); dom.window.close();
  console.log('Desktop cart drawer handles loading, retry, updates, focus and mobile fallback.');
})().catch(error => { console.error(error); process.exitCode = 1; });
