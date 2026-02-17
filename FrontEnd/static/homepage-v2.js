/**
 * Homepage v2 – Carousel hero: auto-advance every 6 seconds.
 * Keeps focus-outline behavior from v1.
 */

(function () {
  const CAROUSEL_INTERVAL_MS = 7500;
  var carouselInitialized = false;

  function playSound(filename) {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent(filename));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (e) {}
  }

  function initCarousel() {
    if (carouselInitialized) return;
    const slides = document.querySelectorAll('.carousel-slide');
    if (!slides.length) return;
    carouselInitialized = true;

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
      clearInterval(intervalId);
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

    document.querySelectorAll('.carousel-cta').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        playSound('click-strong.wav');
        var href = link.getAttribute('href');
        if (href) setTimeout(function () { window.location.href = href; }, 200);
      });
    });
    // Top nav: Tutorials (and Feedback if present) — homepage has static bar, authBarInit may not run
    document.querySelectorAll('.tutorials-nav-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { playSound('click-tiny.wav'); });
    });
    var feedbackBtn = document.getElementById('feedback-btn');
    if (feedbackBtn) {
      feedbackBtn.addEventListener('click', function () { playSound('click-tiny.wav'); });
    }
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
