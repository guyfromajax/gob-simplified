/**
 * Homepage v2 – Carousel hero: auto-advance every 6 seconds.
 * Keeps focus-outline behavior from v1.
 */

(function () {
  const CAROUSEL_INTERVAL_MS = 6000;

  function initCarousel() {
    const slides = document.querySelectorAll('.carousel-slide');
    if (!slides.length) return;

    let currentIndex = 0;
    let intervalId;

    function goTo(index) {
      currentIndex = (index + slides.length) % slides.length;
      slides.forEach(function (s, i) {
        s.classList.toggle('active', i === currentIndex);
        s.setAttribute('aria-hidden', i !== currentIndex);
      });
    }

    function next() {
      goTo(currentIndex + 1);
    }

    function prev() {
      goTo(currentIndex - 1);
    }

    function startInterval() {
      intervalId = setInterval(next, CAROUSEL_INTERVAL_MS);
    }

    function resetInterval() {
      clearInterval(intervalId);
      startInterval();
    }

    goTo(0);
    startInterval();

    var prevBtn = document.querySelector('.carousel-arrow-prev');
    var nextBtn = document.querySelector('.carousel-arrow-next');
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        prev();
        resetInterval();
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        next();
        resetInterval();
      });
    }

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        clearInterval(intervalId);
      } else {
        startInterval();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCarousel);
  } else {
    initCarousel();
  }

  // Focus outlines (same as v1)
  document.addEventListener('mousedown', function () {
    document.body.classList.add('using-mouse');
  });
  document.addEventListener('keydown', function () {
    document.body.classList.remove('using-mouse');
  });
})();
