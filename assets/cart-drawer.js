(() => {
  const toggle = document.querySelector('[data-cart-drawer-toggle]');
  const drawer = document.querySelector('[data-cart-drawer]');
  const body = drawer && drawer.querySelector('[data-drawer-body]');
  if (!toggle || !drawer || !body || typeof drawer.showModal !== 'function') return;
  const desktop = window.matchMedia('(min-width: 621px)');
  let request, sequence = 0;

  const syncToggle = () => {
    if (desktop.matches) {
      toggle.setAttribute('aria-haspopup', 'dialog');
      toggle.setAttribute('aria-controls', 'cart-drawer');
      toggle.setAttribute('aria-expanded', String(drawer.open));
    } else {
      toggle.removeAttribute('aria-haspopup');
      toggle.removeAttribute('aria-controls');
      toggle.removeAttribute('aria-expanded');
    }
  };
  const load = async () => {
    if (request) request.abort();
    request = new AbortController();
    const current = ++sequence;
    body.setAttribute('aria-busy', 'true');
    body.innerHTML = '<p class="drawer-loading">Loading your cart…</p>';
    try {
      const url = new URL(toggle.href, location.href);
      url.searchParams.set('preview', '1');
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: request.signal, headers: {'Accept': 'text/html'}});
      if (!response.ok || !(response.headers.get('content-type') || '').includes('text/html')) throw new Error('Cart preview unavailable');
      const html = await response.text();
      if (current !== sequence || !drawer.open) return;
      const fragment = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-drawer-preview]');
      if (!fragment) throw new Error('Invalid cart preview');
      body.replaceChildren(fragment);
      const count = Number(fragment.dataset.count);
      const badge = document.querySelector('[data-cart-badge]');
      if (badge && Number.isInteger(count) && count >= 0) { badge.textContent = count; badge.hidden = count === 0; }
    } catch (error) {
      if (error.name === 'AbortError' || current !== sequence || !drawer.open) return;
      body.innerHTML = '<div class="drawer-error"><p>We couldn’t load your cart just now.</p><button type="button" data-drawer-retry>Try again</button></div>';
    } finally {
      if (current === sequence) body.setAttribute('aria-busy', 'false');
    }
  };
  toggle.addEventListener('click', event => {
    if (!desktop.matches || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || toggle.hasAttribute('download') || (toggle.target && toggle.target !== '_self')) return;
    if (drawer.open) { event.preventDefault(); return; }
    try { drawer.showModal(); } catch (_) { return; } // Keep the normal link if a dialog cannot be opened.
    event.preventDefault();
    document.body.classList.add('cart-drawer-open');
    syncToggle();
    const close = drawer.querySelector('[data-drawer-close]');
    if (close) close.focus({preventScroll: true});
    load();
  });
  drawer.addEventListener('click', event => {
    if (event.target.closest('[data-drawer-close]')) { drawer.close(); return; }
    if (event.target.closest('[data-drawer-retry]')) {
      drawer.querySelector('[data-drawer-close]').focus({preventScroll: true});
      load();
      return;
    }
    if (event.target === drawer) {
      const rect = drawer.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) drawer.close();
    }
  });
  drawer.addEventListener('close', () => {
    sequence++;
    if (request) request.abort();
    body.setAttribute('aria-busy', 'false');
    document.body.classList.remove('cart-drawer-open');
    syncToggle();
    toggle.focus({preventScroll: true});
  });
  document.addEventListener('cart:updated', () => { if (drawer.open) load(); });
  window.addEventListener('resize', () => {
    if (!desktop.matches && drawer.open) drawer.close();
    syncToggle();
  });
  syncToggle();
})();
