(() => {
  const feedback = document.getElementById('cart-feedback');
  if (!feedback) return;
  const message = feedback.querySelector('[data-feedback-message]');
  let hideTimer, finishTimer;
  const animateChange = element => {
    if (!element) return;
    element.classList.remove('cart-changed');
    void element.offsetWidth;
    element.classList.add('cart-changed');
  };
  const hideLater = () => {
    clearTimeout(hideTimer);
    clearTimeout(finishTimer);
    feedback.classList.remove('cart-feedback--leaving');
    hideTimer = setTimeout(() => {
      feedback.classList.add('cart-feedback--leaving');
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      finishTimer = setTimeout(() => { feedback.hidden = true; }, reduced ? 0 : 220);
    }, 5000);
  };
  if (!feedback.hidden) hideLater();
  document.addEventListener('submit', async event => {
      const form = event.target;
      if (!form.matches('[data-add-form]')) return;
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
        if (result.success) animateChange(quantity);
        const badge = document.querySelector('[data-cart-badge]');
        if (badge) { badge.textContent = result.cartCount; badge.hidden = result.cartCount <= 0; if (result.success) animateChange(badge); }
        message.textContent = result.message;
        feedback.classList.toggle('cart-feedback--error', !result.success);
      } catch (_) {
        message.textContent = 'We could not confirm the cart update. Refresh the page to check your cart before trying again.';
        feedback.classList.add('cart-feedback--error');
      } finally {
        const wishlistFeedback = document.getElementById('wishlist-feedback');
        if (wishlistFeedback) wishlistFeedback.hidden = true;
        feedback.classList.remove('cart-feedback--enter', 'cart-feedback--leaving');
        feedback.hidden = true;
        void feedback.offsetWidth;
        feedback.hidden = false;
        feedback.classList.add('cart-feedback--enter');
        hideLater();
        button.disabled = false;
      }
  });
})();
