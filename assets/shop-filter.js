(() => {
  const form = document.querySelector('.category-form');
  if (!form) return;
  const clearLink = form.querySelector('.category-clear');
  const error = form.querySelector('[data-filter-error]');
  const checkboxSelector = 'input[type="checkbox"][name="category[]"]';
  const checkboxes = () => Array.from(form.querySelectorAll(checkboxSelector));
  let applied = checkboxes().filter(box => box.checked).map(box => box.value);
  let appliedQuery = form.querySelector('input[name="q"]')?.value || '';
  let appliedSort = document.querySelector('[data-sort-select]')?.value || 'recommended';
  let controller, sequence = 0;

  const apply = async (url, pushHistory, focusSearch = false, changingSort = false) => {
    if (controller) controller.abort();
    controller = new AbortController();
    const current = ++sequence;
    const initialSearch = document.querySelector('.shop-search .search-form input[name="q"]');
    const initialValue = initialSearch ? initialSearch.value : '';
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
      const nextSortField = nextForm.querySelector('input[name="sort"]');
      let currentSortField = form.querySelector('input[name="sort"]');
      if (nextSortField && !currentSortField) { currentSortField = document.createElement('input'); currentSortField.type = 'hidden'; currentSortField.name = 'sort'; form.appendChild(currentSortField); }
      if (nextSortField) currentSortField.value = nextSortField.value;
      else if (currentSortField) currentSortField.remove();
      checkboxes().forEach(box => { box.checked = selected.includes(box.value); });
      applied = selected;
      appliedQuery = query ? query.value : '';
      clearLink.hidden = nextClear.hidden;
      clearLink.setAttribute('href', nextClear.getAttribute('href'));
      const oldSearch = previousResults.querySelector('.search-form input[name="q"]');
      const nextSearch = nextResults.querySelector('.search-form input[name="q"]');
      const nextSearchClear = nextResults.querySelector('[data-clear-search]');
      const oldSort = previousResults.querySelector('[data-sort-select]');
      const nextSort = nextResults.querySelector('[data-sort-select]');
      appliedSort = nextSort ? nextSort.value : 'recommended';
      const restoreSortFocus = oldSort && document.activeElement === oldSort;
      const restoreFocus = focusSearch || (oldSearch && document.activeElement === oldSearch);
      // Do not discard text typed while the request was in flight.
      if (oldSearch && nextSearch && oldSearch.value !== initialValue) {
        nextSearch.value = oldSearch.value;
        if (nextSearchClear) nextSearchClear.hidden = !nextSearch.value;
      }
      previousResults.replaceWith(nextResults);
      if (restoreFocus && nextSearch) nextSearch.focus({preventScroll: true});
      else if (restoreSortFocus && nextSort) nextSort.focus({preventScroll: true});
      if (pushHistory) history.pushState(null, '', url.pathname + url.search + location.hash);
    } catch (err) {
      if (err.name === 'AbortError' || current !== sequence) return;
      if (!pushHistory) { location.reload(); return; }
      checkboxes().forEach(box => { box.checked = applied.includes(box.value); });
      const sort = document.querySelector('[data-sort-select]');
      if (sort) sort.value = appliedSort;
      if (focusSearch) {
        const search = document.querySelector('.shop-search .search-form input[name="q"]');
        const clear = document.querySelector('[data-clear-search]');
        if (search && search.value === '') { search.value = appliedQuery; if (clear) clear.hidden = !search.value; search.focus({preventScroll: true}); }
      }
      error.textContent = focusSearch ? 'Could not clear the search. Please try again.' : changingSort ? 'Could not update the sort order. Please try again.' : 'Could not update the categories. Please try again.';
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
    const search = document.querySelector('.shop-search .search-form input[name="q"]');
    if (search && search.value.trim()) url.searchParams.set('q', search.value.trim());
    else url.searchParams.delete('q');
    const sort = document.querySelector('[data-sort-select]');
    if (sort && sort.value !== 'recommended') url.searchParams.set('sort', sort.value);
    else url.searchParams.delete('sort');
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
  document.addEventListener('change', event => {
    if (event.target.matches('[data-sort-select]')) apply(filterUrl(), true, false, true);
  });
  document.addEventListener('input', event => {
    if (!event.target.matches('#search')) return;
    const clear = event.target.closest('.search-form').querySelector('[data-clear-search]');
    if (clear) clear.hidden = !event.target.value;
  });
  document.addEventListener('click', event => {
    const clear = event.target.closest('[data-clear-search]');
    if (!clear) return;
    event.preventDefault();
    const search = clear.closest('.search-form').querySelector('input[name="q"]');
    if (!search) return;
    search.value = '';
    clear.hidden = true;
    search.focus({preventScroll: true});
    apply(filterUrl(), true, true);
  });
  window.addEventListener('popstate', () => apply(new URL(location.href), false));
})();
