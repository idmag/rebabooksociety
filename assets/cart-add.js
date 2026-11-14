(() => {
  document.querySelectorAll('[data-add-form]').forEach(form => {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"], button:not([type])');
      const feedback = form.querySelector('.cart-feedback');
      const message = feedback.querySelector('[data-feedback-message]');
      button.disabled = true;
      try {
        const response = await fetch(form.action || location.href, {
          method: 'POST', body: new FormData(form), credentials: 'same-origin',
          headers: {'Accept': 'application/json'}
        });
        if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Cart response unavailable');
        const result = await response.json();
        form.querySelector('[data-cart-quantity]').textContent = `${result.quantity} in cart`;
        const badge = document.querySelector('.bag-link span');
        if (badge) badge.textContent = result.cartCount;
        message.textContent = result.message;
        feedback.classList.toggle('cart-feedback--error', !result.success);
      } catch (_) {
        message.textContent = 'We could not confirm the cart update. Refresh the page to check your cart before trying again.';
        feedback.classList.add('cart-feedback--error');
      } finally {
        feedback.hidden = false;
        button.disabled = false;
      }
    });
  });
})();
