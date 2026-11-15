// Run with `node tests/mobile_filters_ui.js`.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const toggleHandlers = {}, docHandlers = {}, windowHandlers = {};
const classes = new Set();
let expanded = 'false', focused = false, mobile = true;
const toggle = {
  addEventListener: (name, fn) => { toggleHandlers[name] = fn; },
  getAttribute: () => expanded,
  setAttribute: (_, value) => { expanded = value; },
  focus: options => { assert.equal(options.preventScroll, true); focused = true; },
  contains: target => target === 'toggle'
};
const panel = {
  classList: {remove: name => classes.delete(name), toggle: (name, on) => on ? classes.add(name) : classes.delete(name)},
  contains: target => target === 'panel'
};
const context = {
  document: {
    querySelector: selector => selector === '[data-filter-toggle]' ? toggle : null,
    getElementById: id => id === 'shop-filters' ? panel : null,
    addEventListener: (name, fn) => { docHandlers[name] = fn; }
  },
  window: {addEventListener: (name, fn) => { windowHandlers[name] = fn; }, matchMedia: () => ({matches: mobile})}
};
vm.runInNewContext(fs.readFileSync('assets/mobile-filters.js', 'utf8'), context);
assert.equal(expanded, 'false');
assert.equal(classes.has('is-open'), false);
toggleHandlers.click();
assert.equal(expanded, 'true');
assert.equal(classes.has('is-open'), true);
docHandlers.click({target: 'panel'});
assert.equal(expanded, 'true');
docHandlers.click({target: 'toggle'});
assert.equal(expanded, 'true');
docHandlers.click({target: 'outside'});
assert.equal(expanded, 'false');
assert.equal(classes.has('is-open'), false);
toggleHandlers.click();
let prevented = false;
docHandlers.keydown({key: 'Escape', preventDefault: () => { prevented = true; }});
assert(prevented);
assert(focused);
assert.equal(expanded, 'false');
toggleHandlers.click();
windowHandlers.resize();
assert.equal(expanded, 'true');
mobile = false;
windowHandlers.resize();
assert.equal(expanded, 'false');
assert.equal(classes.has('is-open'), false);
console.log('Mobile category panel opens and closes accessibly.');
