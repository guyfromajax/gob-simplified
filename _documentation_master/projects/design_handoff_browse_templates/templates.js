/* GOB browse templates — reference behaviour for the wide-table card (.xs).
   Edge fades, position map, ◂ ▸ paging and group jumps. No framework. */
(function () {
  function initXS(card) {
    if (card._xsUpdate) { card._xsUpdate(); return; }
    var body = card.querySelector('.xs-body');
    if (!body) return;
    var pin = card.querySelector('th.pin');
    var map = card.querySelector('.xs-map i');
    var prev = card.querySelector('[data-xs="prev"]');
    var next = card.querySelector('[data-xs="next"]');
    var jumps = card.querySelectorAll('[data-xs-group]');
    function pinW() { return pin ? pin.getBoundingClientRect().width : 0; }
    function update() {
      var max = body.scrollWidth - body.clientWidth, x = body.scrollLeft;
      card.style.setProperty('--pin-w', pinW() + 'px');
      card.classList.toggle('can-l', x > 1);
      card.classList.toggle('can-r', x < max - 1);
      if (prev) prev.disabled = x <= 1;
      if (next) next.disabled = x >= max - 1;
      if (map) {
        var w = body.clientWidth / body.scrollWidth;
        map.style.setProperty('--w', (w * 100) + '%');
        map.style.setProperty('--x', (max ? (x / max) * (1 - w) * 100 : 0) + '%');
      }
      var edge = x + pinW() + 8, active = null;
      jumps.forEach(function (b) {
        var th = card.querySelector('th[data-group="' + b.dataset.xsGroup + '"]');
        if (th && th.offsetLeft <= edge) active = b;
      });
      jumps.forEach(function (b) { b.classList.toggle('on', b === active); });
    }
    function page(dir) {
      body.scrollBy({ left: dir * (body.clientWidth - pinW()) * 0.8, behavior: 'smooth' });
    }
    if (prev) prev.addEventListener('click', function () { page(-1); });
    if (next) next.addEventListener('click', function () { page(1); });
    jumps.forEach(function (b) {
      b.addEventListener('click', function () {
        var th = card.querySelector('th[data-group="' + b.dataset.xsGroup + '"]');
        if (th) body.scrollTo({ left: th.offsetLeft - pinW(), behavior: 'smooth' });
      });
    });
    body.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    card._xsUpdate = update;
    update();
    if (card.dataset.startX) { body.scrollLeft = +card.dataset.startX; update(); }
  }
  function boot() { document.querySelectorAll('.xs').forEach(initXS); }
  if (document.readyState !== 'loading') boot(); else document.addEventListener('DOMContentLoaded', boot);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(boot);
})();
