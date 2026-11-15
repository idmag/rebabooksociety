(() => {
  const shelf = document.getElementById('featured-books');
  const controls = document.querySelector('.featured-carousel-controls');
  if (!shelf || !controls || shelf.children.length < 2) return;

  const previous = controls.querySelector('[data-featured-prev]');
  const next = controls.querySelector('[data-featured-next]');
  const update = () => {
    previous.disabled = shelf.scrollLeft <= 1;
    next.disabled = shelf.scrollLeft >= shelf.scrollWidth - shelf.clientWidth - 1;
  };
  const move = direction => {
    const cards = shelf.querySelectorAll('.book-card');
    const step = cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : shelf.clientWidth;
    shelf.scrollBy({left: direction * step, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  };
  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  shelf.addEventListener('scroll', update, {passive: true});
  window.addEventListener('resize', update);
  controls.hidden = false;
  update();
})();
