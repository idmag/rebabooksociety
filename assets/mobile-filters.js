(() => {
  const toggle = document.querySelector('[data-filter-toggle]');
  const panel = document.getElementById('shop-filters');
  if (!toggle || !panel) return;
  const close = restoreFocus => {
    panel.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
    if (restoreFocus) toggle.focus({preventScroll: true});
  };
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    panel.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('click', event => {
    if (toggle.getAttribute('aria-expanded') === 'true' && !panel.contains(event.target) && !toggle.contains(event.target)) close(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') { event.preventDefault(); close(true); }
  });
  window.addEventListener('resize', () => {
    if (!window.matchMedia('(max-width: 620px)').matches) close(false);
  });
})();
