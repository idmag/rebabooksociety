(() => {
  const feedback = document.getElementById('cart-feedback');
  if (!feedback) return;
  const message = feedback.querySelector('[data-feedback-message]');
  let hideTimer;
  const hideLater = () => {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { feedback.hidden = true; }, 5000);
  };
  if (!feedback.hidden) hideLater();
  document.querySelectorAll('[data-add-form]').forEach(form => {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"], button:not([type])');
      button.disabled = true;
      try {
        const response = await fetch(form.action || location.href, {
          method: 'POST', body: new FormData(form), credentials: 'same-origin',
          headers: {'Accept': 'application/json'}
        });
        if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Cart response unavailable');
        const result = await response.json();
        const quantity = form.querySelector('[data-cart-quantity]');
        quantity.textContent = `${result.quantity} in cart`;
        quantity.hidden = result.quantity <= 0;
        const badge = document.querySelector('[data-cart-badge]');
        if (badge) { badge.textContent = result.cartCount; badge.hidden = result.cartCount <= 0; }
        message.textContent = result.message;
        feedback.classList.toggle('cart-feedback--error', !result.success);
      } catch (_) {
        message.textContent = 'We could not confirm the cart update. Refresh the page to check your cart before trying again.';
        feedback.classList.add('cart-feedback--error');
      } finally {
        feedback.hidden = false;
        hideLater();
        button.disabled = false;
      }
    });
  });
})();
