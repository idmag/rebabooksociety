// Run with `node tests/shop_actions_ui.js`. New result cards must remain interactive.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

(async () => {
  const listeners = [];
  function element() {
    const classes = new Set();
    return {hidden: true, textContent: '', offsetWidth: 20, classList: {add: (...names) => names.forEach(n => classes.add(n)), remove: (...names) => names.forEach(n => classes.delete(n)), toggle: (name, value) => value ? classes.add(name) : classes.delete(name)}};
  }
  const cartFeedback = element(), wishFeedback = element(), cartMessage = element(), wishMessage = element(), cartBadge = element(), wishBadge = element();
  cartFeedback.querySelector = () => cartMessage;
  wishFeedback.querySelector = () => wishMessage;
  const document = {
    getElementById: id => id === 'cart-feedback' ? cartFeedback : wishFeedback,
    addEventListener: (name, handler) => { if (name === 'submit') listeners.push(handler); },
    querySelector: selector => selector === '[data-cart-badge]' ? cartBadge : selector === '[data-wishlist-badge]' ? wishBadge : null,
    querySelectorAll: () => []
  };
  const context = {
    document, window: {matchMedia: () => ({matches: false})}, location: {href: '/shop'},
    FormData: class { constructor(form) { this.form = form; } }, setTimeout: () => 1, clearTimeout() {},
    fetch: async (_, options) => ({ok: true, headers: {get: () => 'application/json'}, json: async () => options.body.form.kind === 'cart' ? {quantity: 1, cartCount: 1, message: 'Added to cart', success: true} : {saved: true, count: 1, totalCount: 1, message: 'Added to wishlist'}})
  };
  vm.runInNewContext(fs.readFileSync('assets/cart-add.js', 'utf8'), context);
  vm.runInNewContext(fs.readFileSync('assets/wishlist.js', 'utf8'), context);
  assert.equal(listeners.length, 2);

  // These forms are created only after the scripts run, as happens after filtering.
  const quantity = element(), cartButton = {disabled: false};
  const cartForm = {kind: 'cart', action: '/shop?category=Drama', matches: s => s === '[data-add-form]', querySelector: s => s.startsWith('button') ? cartButton : quantity};
  let prevented = 0;
  await Promise.all(listeners.map(fn => fn({target: cartForm, preventDefault: () => prevented++})));
  assert.equal(prevented, 1);
  assert.equal(quantity.textContent, '1 in cart');
  assert.equal(quantity.hidden, false);
  assert.equal(cartBadge.textContent, 1);

  const attrs = {}, nextState = {value: '1'}, button = {setAttribute: (name, value) => { attrs[name] = value; }};
  const wishlistForm = {kind: 'wishlist', action: '/shop?category=Drama', dataset: {title: 'A Book'}, matches: s => s === '[data-wishlist-form]', querySelector: s => s === 'button' ? button : s === '[name="set"]' ? nextState : null};
  prevented = 0;
  await Promise.all(listeners.map(fn => fn({target: wishlistForm, preventDefault: () => prevented++})));
  assert.equal(prevented, 1);
  assert.equal(attrs['aria-pressed'], 'true');
  assert.equal(nextState.value, '0');
  assert.equal(wishBadge.textContent, 1);
  assert.equal(wishFeedback.hidden, false);
  console.log('Cart and wishlist work on dynamically filtered cards.');
})().catch(err => { console.error(err); process.exitCode = 1; });
