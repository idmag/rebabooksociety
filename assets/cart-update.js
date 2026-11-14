(() => {
  const form = document.querySelector('[data-cart-form]');
  if (!form) return;
  const status = form.querySelector('[data-cart-status]');
  const checkout = document.querySelector('[data-checkout]');
  let timer, dirty = false, saving = false;
  const animateChange = element => {
    if (!element) return;
    element.classList.remove('cart-changed');
    void element.offsetWidth;
    element.classList.add('cart-changed');
  };

  const inputs = () => Array.from(form.querySelectorAll('input[type="number"]'));
  const save = async () => {
    clearTimeout(timer);
    if (saving || !dirty) return !dirty;
    if (!form.checkValidity()) { status.textContent = 'Enter a quantity between 0 and 20.'; return false; }
    const data = new FormData(form);
    saving = true;
    inputs().forEach(input => { input.disabled = true; });
    form.querySelectorAll('button').forEach(button => { button.disabled = true; });
    status.textContent = 'Updating your bag…';
    try {
      const response = await fetch(form.action || location.href, {method:'POST', body:data, credentials:'same-origin', headers:{'Accept':'application/json'}});
      if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Update failed');
      const result = await response.json();
      form.querySelectorAll('[data-cart-row]').forEach(row => {
        const item = result.items[row.dataset.cartRow];
        if (!item) { row.remove(); return; }
        row.querySelector('input[type="number"]').value = item.quantity;
        row.querySelector('[data-unit-price]').textContent = item.unitPrice;
        const line = row.querySelector('[data-line-total]');
        if (line.textContent !== item.lineTotal) { line.textContent = item.lineTotal; animateChange(line); }
        const warning = row.querySelector('[data-stock-warning]');
        warning.hidden = item.stock === null || item.quantity <= item.stock;
        warning.textContent = item.stock === 0 ? 'Out of stock' : `Available: ${item.stock}`;
      });
      const subtotal = document.querySelector('[data-cart-subtotal]');
      if (subtotal.textContent !== result.subtotal) { subtotal.textContent = result.subtotal; animateChange(subtotal); }
      const badge = document.querySelector('[data-cart-badge]');
      if (badge) { if (Number(badge.textContent) !== result.cartCount) animateChange(badge); badge.textContent = result.cartCount; badge.hidden = result.cartCount <= 0; }
      dirty = false;
      status.textContent = 'Your bag has been updated.';
      animateChange(status);
      if (!result.cartCount) location.reload();
      return true;
    } catch (_) {
      status.textContent = 'Could not update your bag. Please try Update bag again.';
      animateChange(status);
      return false;
    } finally {
      saving = false;
      inputs().forEach(input => { input.disabled = false; });
      form.querySelectorAll('button').forEach(button => { button.disabled = false; });
    }
  };
  form.addEventListener('input', event => {
    if (!event.target.matches('input[type="number"]')) return;
    dirty = true;
    status.textContent = 'Waiting to update…';
    clearTimeout(timer);
    timer = setTimeout(save, 1000);
  });
  form.addEventListener('submit', async event => {
    if (saving) { event.preventDefault(); return; }
    clearTimeout(timer);
    const submitter = event.submitter;
    if (submitter && submitter.name === 'remove_id' && dirty && form.checkValidity()) {
      event.preventDefault();
      if (await save() && submitter.isConnected) form.requestSubmit(submitter);
    }
  });
  if (checkout) checkout.addEventListener('click', async event => {
    if (saving) { event.preventDefault(); return; }
    if (dirty) {
      event.preventDefault();
      if (await save() && document.querySelector('[data-cart-row]')) location.href = checkout.href;
    }
  });
})();
