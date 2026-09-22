function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

/**
 * Homepage v3 — Sticky nav CTA, FAQ accordion, scroll entrance animations.
 * No dependencies. Vanilla JS, passive listeners throughout.
 */
(function () {
  'use strict';

  /* ─── Sound helper ─── */
  function playSound(filename) {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent(filename));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (e) {}
  }

  /* ─── Sticky nav + nav CTA visibility ─── */
  function initStickyNav() {
    var nav    = document.getElementById('auth-bar');
    var heroCta = document.getElementById('hero-cta');
    var navCta  = document.getElementById('nav-cta');
    if (!nav) return;

    var heroCtaBottom = 0;

    function measureHeroCta() {
      if (heroCta) {
        var rect = heroCta.getBoundingClientRect();
        heroCtaBottom = rect.bottom + window.scrollY;
      }
    }

    function onScroll() {
      var scrollY = window.scrollY || window.pageYOffset;

      /* Darken nav background after first 20px */
      if (scrollY > 20) {
        nav.classList.add('nav-scrolled');
      } else {
        nav.classList.remove('nav-scrolled');
      }

      /* Show nav CTA once hero CTA has scrolled out of view */
      if (navCta) {
        if (scrollY > heroCtaBottom) {
          navCta.classList.add('nav-cta-visible');
        } else {
          navCta.classList.remove('nav-cta-visible');
        }
      }
    }

    measureHeroCta();
    window.addEventListener('resize', measureHeroCta, { passive: true });
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ─── Scroll entrance animations ─── */
  function initScrollAnimations() {
    /* Attach anim class to all target elements */
    var selectors = [
      '.pillar-card',
      '.feature-card',
      '.community-screenshot-wrap',
      '.community-cta-wrap',
      '.faq-item',
      '.footer-cta-inner',
      '.deepdive-header',
      '.community-header',
      '.pillars .section-eyebrow'
    ];

    selectors.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        el.classList.add('anim-fade-up');
      });
    });

    if (!('IntersectionObserver' in window)) {
      /* Fallback: just show everything */
      document.querySelectorAll('.anim-fade-up').forEach(function (el) {
        el.classList.add('anim-visible');
      });
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('anim-visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -40px 0px'
    });

    document.querySelectorAll('.anim-fade-up').forEach(function (el) {
      observer.observe(el);
    });
  }

  /* ─── Alpha CTA labels / hrefs (logged-out default in markup) ─── */
  function hasStoredAuth() {
    try {
      return !!(localStorage.getItem('auth_token') && localStorage.getItem('auth_user'));
    } catch (e) {
      return false;
    }
  }

  function signupHref() {
    var params = liveParams();
    var out = emptyParams();
    var utm = params.get('utm_source');
    var ref = params.get('ref');
    if (utm) out.set('utm_source', utm);
    if (ref) out.set('ref', ref);
    var q = out.toString();
    return q ? '/signup.html?' + q : '/signup.html';
  }

  function initAlphaCtas() {
    var loggedIn = hasStoredAuth();
    var href = loggedIn ? './mode-select.html' : signupHref();
    var label = loggedIn ? 'Play the Alpha' : 'Get Alpha Access';
    ['nav-cta', 'hero-cta', 'final-cta'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.setAttribute('href', href);
      el.textContent = label;
      el.setAttribute('aria-label', label);
    });
    document.querySelectorAll('.alpha-code-micro').forEach(function (el) {
      el.hidden = loggedIn;
    });
  }

  /* ─── CTA sound effects ─── */
  function initCtaSounds() {
    document.querySelectorAll('.hero-cta, .nav-cta, .community-cta').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        playSound('click-strong.wav');
        var href = el.getAttribute('href');
        if (href) setTimeout(function () { window.location.href = href; }, 180);
      });
    });

    /* Tutorials nav */
    document.querySelectorAll('.nav-tutorials-link').forEach(function (btn) {
      btn.addEventListener('click', function () { playSound('click-tiny.wav'); });
    });
  }

  /* ─── Mouse/keyboard focus outline behavior ─── */
  function initFocusOutlines() {
    document.addEventListener('mousedown', function () {
      document.body.classList.add('using-mouse');
    });
    document.addEventListener('keydown', function () {
      document.body.classList.remove('using-mouse');
    });
  }

  /* ─── Init ─── */
  function init() {
    initAlphaCtas();
    initStickyNav();
    initScrollAnimations();
    initCtaSounds();
    initFocusOutlines();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
