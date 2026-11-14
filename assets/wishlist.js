(() => {
  const feedback = document.getElementById('wishlist-feedback');
  if (!feedback) return;
  const message = feedback.querySelector('[data-wishlist-message]');
  let hideTimer, finishTimer, pending = 0;
  const clearForm = document.querySelector('[data-clear-wishlist]');
  const clearButton = clearForm && clearForm.querySelector('button');
  if (clearForm) clearForm.addEventListener('submit', event => {
    if (!window.confirm('Remove all books from your wishlist, including unavailable books?')) event.preventDefault();
    else {
      clearButton.disabled = true;
      document.querySelectorAll('[data-wishlist-form] button').forEach(button => { button.disabled = true; });
    }
  });
  const showMessage = (text, isError) => {
    clearTimeout(hideTimer);
    clearTimeout(finishTimer);
    const cartFeedback = document.getElementById('cart-feedback');
    if (cartFeedback) cartFeedback.hidden = true;
    message.textContent = text;
    feedback.classList.toggle('cart-feedback--error', isError);
    feedback.classList.remove('cart-feedback--enter', 'cart-feedback--leaving');
    feedback.hidden = true;
    void feedback.offsetWidth;
    feedback.hidden = false;
    feedback.classList.add('cart-feedback--enter');
    hideTimer = setTimeout(() => {
      feedback.classList.add('cart-feedback--leaving');
      finishTimer = setTimeout(() => { feedback.hidden = true; }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 220);
    }, 5000);
  };
  document.addEventListener('submit', async event => {
      const form = event.target;
      if (!form.matches('[data-wishlist-form]')) return;
      event.preventDefault();
      const button = form.querySelector('button');
      pending++;
      document.querySelectorAll('[data-wishlist-form] button').forEach(item => { item.disabled = true; });
      if (clearButton) clearButton.disabled = true;
      try {
        const response = await fetch(form.action || location.href, {method:'POST', body:new FormData(form), credentials:'same-origin', headers:{'Accept':'application/json'}});
        if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Wishlist update failed');
        const result = await response.json();
        form.querySelector('[name="set"]').value = result.saved ? '0' : '1';
        button.setAttribute('aria-pressed', String(result.saved));
        button.setAttribute('aria-label', `${result.saved ? 'Remove' : 'Add'} ${form.dataset.title} ${result.saved ? 'from' : 'to'} wishlist`);
        const label = form.querySelector('[data-wishlist-label]');
        if (label) label.textContent = result.saved ? 'Saved to Wishlist' : 'Add to Wishlist';
        const badge = document.querySelector('[data-wishlist-badge]');
        if (badge) { badge.textContent = result.count; badge.hidden = result.count === 0; }
        if (clearForm) clearForm.hidden = result.totalCount === 0;
        const page = document.querySelector('[data-wishlist-page]');
        if (page && !result.saved) {
          const card = form.closest('.book-card');
          if (card) card.remove();
          page.querySelector('[data-wishlist-empty]').hidden = !!page.querySelector('.book-card');
        }
        showMessage(result.message, false);
      } catch (_) {
        showMessage('We could not update your wishlist. Please refresh and try again.', true);
      } finally {
        pending--;
        if (pending === 0) {
          document.querySelectorAll('[data-wishlist-form] button').forEach(item => { item.disabled = false; });
          if (clearButton) clearButton.disabled = false;
        }
      }
  });
})();
