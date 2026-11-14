(() => {
  const form = document.querySelector('.category-form');
  if (!form) return;
  const clearLink = form.querySelector('.category-clear');
  const error = form.querySelector('[data-filter-error]');
  const checkboxSelector = 'input[type="checkbox"][name="category[]"]';
  const checkboxes = () => Array.from(form.querySelectorAll(checkboxSelector));
  let applied = checkboxes().filter(box => box.checked).map(box => box.value);
  let controller, sequence = 0;

  const apply = async (url, pushHistory) => {
    if (controller) controller.abort();
    controller = new AbortController();
    const current = ++sequence;
    const results = document.querySelector('.shop-results');
    if (results) results.setAttribute('aria-busy', 'true');
    error.hidden = true;
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: {'Accept': 'text/html'}});
      if (!response.ok) throw new Error('Could not load filters');
      const html = await response.text();
      if (current !== sequence) return;
      const page = new DOMParser().parseFromString(html, 'text/html');
      const nextResults = page.querySelector('.shop-results');
      const nextForm = page.querySelector('.category-form');
      const nextClear = nextForm && nextForm.querySelector('.category-clear');
      const previousResults = document.querySelector('.shop-results');
      if (!nextResults || !nextForm || !nextClear || !previousResults) throw new Error('Invalid filter response');
      const selected = Array.from(nextForm.querySelectorAll(checkboxSelector)).filter(box => box.checked).map(box => box.value);
      const query = nextForm.querySelector('input[name="q"]');
      let currentQuery = form.querySelector('input[name="q"]');
      if (query && !currentQuery) { currentQuery = document.createElement('input'); currentQuery.type = 'hidden'; currentQuery.name = 'q'; form.appendChild(currentQuery); }
      if (query) currentQuery.value = query.value;
      else if (currentQuery) currentQuery.remove();
      checkboxes().forEach(box => { box.checked = selected.includes(box.value); });
      applied = selected;
      clearLink.hidden = nextClear.hidden;
      clearLink.setAttribute('href', nextClear.getAttribute('href'));
      previousResults.replaceWith(nextResults);
      if (pushHistory) history.pushState(null, '', url.pathname + url.search + location.hash);
    } catch (err) {
      if (err.name === 'AbortError' || current !== sequence) return;
      if (!pushHistory) { location.reload(); return; }
      checkboxes().forEach(box => { box.checked = applied.includes(box.value); });
      error.textContent = 'Could not update the categories. Please try again.';
      error.hidden = false;
    } finally {
      if (current === sequence) {
        const currentResults = document.querySelector('.shop-results');
        if (currentResults) currentResults.removeAttribute('aria-busy');
      }
    }
  };
  const filterUrl = () => {
    const url = new URL(form.action, location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();
    const search = document.querySelector('.shop-search input[name="q"]');
    if (search && search.value.trim()) url.searchParams.set('q', search.value.trim());
    else url.searchParams.delete('q');
    url.hash = '';
    return url;
  };
  form.addEventListener('change', event => {
    if (event.target.matches(checkboxSelector)) apply(filterUrl(), true);
  });
  clearLink.addEventListener('click', event => {
    event.preventDefault();
    checkboxes().forEach(box => { box.checked = false; });
    apply(filterUrl(), true);
  });
  window.addEventListener('popstate', () => apply(new URL(location.href), false));
})();
