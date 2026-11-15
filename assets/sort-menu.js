(() => {
  let openMenu = null;

  const close = restoreFocus => {
    if (!openMenu) return;
    const {root, trigger, menu} = openMenu;
    menu.hidden = true;
    root.classList.remove('sort-open', 'sort-open-up');
    trigger.setAttribute('aria-expanded', 'false');
    openMenu = null;
    if (restoreFocus && root.isConnected) trigger.focus({preventScroll: true});
  };
  const focusOption = (menu, options, index) => {
    const option = options[Math.max(0, Math.min(index, options.length - 1))];
    options.forEach(item => { item.tabIndex = item === option ? 0 : -1; });
    option.focus({preventScroll: true});
    // Keep keyboard focus visible inside the menu without moving the page.
    if (option.offsetTop < menu.scrollTop) menu.scrollTop = option.offsetTop;
    else if (option.offsetTop + option.offsetHeight > menu.scrollTop + menu.clientHeight) menu.scrollTop = option.offsetTop + option.offsetHeight - menu.clientHeight;
  };
  const enhance = () => {
    close(false);
    const select = document.querySelector('[data-sort-select]');
    if (!select || select.dataset.enhanced) return;
    const root = select.closest('.sort-select-wrap');
    if (!root) return;
    const values = Array.from(select.options);
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'sort-trigger';
    trigger.setAttribute('data-sort-trigger', '');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', 'sort-options');
    const current = document.createElement('span');
    current.className = 'sort-current';
    const arrow = document.createElement('span');
    arrow.className = 'sort-trigger-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    trigger.append(current, arrow);
    const menu = document.createElement('div');
    menu.id = 'sort-options';
    menu.className = 'sort-menu';
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', 'Sort books by');
    menu.hidden = true;
    const options = values.map(item => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'sort-option';
      option.setAttribute('role', 'option');
      const text = document.createElement('span');
      text.textContent = item.textContent.trim();
      const check = document.createElement('span');
      check.className = 'sort-check';
      check.setAttribute('aria-hidden', 'true');
      check.textContent = '✓';
      option.append(text, check);
      option.addEventListener('click', () => {
        const changed = select.value !== item.value;
        select.value = item.value;
        sync();
        close(true);
        if (changed) select.dispatchEvent(new Event('change', {bubbles: true}));
      });
      return option;
    });
    menu.append(...options);
    const sync = () => {
      let selected = values.findIndex(item => item.value === select.value);
      if (selected < 0) selected = 0;
      current.textContent = values[selected].textContent.trim();
      trigger.setAttribute('aria-label', 'Sort by: ' + current.textContent);
      options.forEach((item, index) => {
        item.setAttribute('aria-selected', String(index === selected));
        item.tabIndex = index === selected ? 0 : -1;
      });
    };
    const show = () => {
      close(false);
      sync();
      openMenu = {root, trigger, menu};
      menu.hidden = false;
      root.classList.add('sort-open');
      trigger.setAttribute('aria-expanded', 'true');
      const rect = trigger.getBoundingClientRect();
      root.classList.toggle('sort-open-up', window.innerHeight - rect.bottom < Math.min(menu.scrollHeight, 300) + 12 && rect.top > window.innerHeight - rect.bottom);
      focusOption(menu, options, Math.max(0, values.findIndex(item => item.value === select.value)));
    };
    trigger.addEventListener('click', () => { if (openMenu && openMenu.trigger === trigger) close(true); else show(); });
    trigger.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); show(); }
    });
    menu.addEventListener('keydown', event => {
      const index = options.indexOf(document.activeElement);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : Math.max(0, index) + (event.key === 'ArrowDown' ? 1 : -1);
        focusOption(menu, options, next);
      }
    });
    select.addEventListener('change', sync);
    select.addEventListener('shop:sort-sync', sync);
    const label = select.form && select.form.querySelector('label[for="shop-sort"]');
    if (label) label.addEventListener('click', event => { event.preventDefault(); trigger.click(); });
    root.append(trigger, menu);
    select.hidden = true;
    select.dataset.enhanced = 'true';
    root.classList.add('is-enhanced');
    sync();
  };
  document.addEventListener('click', event => { if (openMenu && !openMenu.root.contains(event.target)) close(false); });
  document.addEventListener('focusin', event => { if (openMenu && !openMenu.root.contains(event.target)) close(false); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && openMenu) { event.preventDefault(); close(true); } });
  document.addEventListener('shop:updated', enhance);
  enhance();
})();
