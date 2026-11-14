(() => {
  const form = document.querySelector('.category-form');
  if (!form) return;
  form.addEventListener('change', event => {
    if (event.target.matches('input[type="checkbox"][name="category[]"]')) form.requestSubmit();
  });
})();
