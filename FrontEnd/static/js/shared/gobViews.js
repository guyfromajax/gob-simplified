/**
 * Module views inside franchise-command-center.html.
 * In-page tabs stay as they are. A registered view loads once, stays mounted,
 * and is shown again with ?tab=<view-id> (rail push, sub-tab replace).
 */
(function (global) {
  'use strict';

  var registry = Object.create(null);
  var mounted = Object.create(null);
  var attempts = Object.create(null);

  function ctx() {
    var params;
    try {
      params = global.FranchiseContext && typeof global.FranchiseContext.toSearchParams === 'function'
        ? global.FranchiseContext.toSearchParams()
        : new URLSearchParams(global.location.search);
    } catch (err) {
      params = new URLSearchParams();
    }
    return {
      franchiseId: params.get('franchise_id') || '',
      teamId: params.get('team_id') || params.get('user_team_id') || '',
      store: global.GOBStore || null,
      nav: global.GOBNav || null
    };
  }

  function register(spec) {
    if (!spec || !spec.id) return;
    registry[spec.id] = spec;
  }

  function has(id) {
    return !!registry[id];
  }

  function panel(id) {
    return document.getElementById(id);
  }

  function skeleton(host) {
    var html = '<div class="gob-view-skel" aria-hidden="true"><div class="gob-view-skel-bar"></div>';
    var i;
    for (i = 0; i < 8; i++) html += '<div class="gob-view-skel-row"></div>';
    html += '</div>';
    host.innerHTML = html;
  }

  function errorCard(host, onRetry) {
    host.innerHTML = '<div class="gob-view-error" role="alert">'
      + '<p>This view could not be opened.</p>'
      + '<button type="button" class="gob-view-retry">Retry</button>'
      + '</div>';
    var button = host.querySelector('.gob-view-retry');
    if (button) button.addEventListener('click', onRetry);
  }

  function show(id) {
    var spec = registry[id];
    var host = panel(id);
    if (!host) return Promise.resolve();
    if (!spec) {
      errorCard(host, function () { show(id); });
      return Promise.resolve();
    }
    if (mounted[id]) {
      if (typeof mounted[id].revalidate === 'function') mounted[id].revalidate();
      return Promise.resolve();
    }
    if (host.__gobViewPending) return host.__gobViewPending;
    skeleton(host);
    var attempt = attempts[id] || 0;
    var pending = Promise.resolve().then(function () {
      return spec.module(attempt);
    }).then(function (mod) {
      var mount = mod && (mod.mount || (mod.default && mod.default.mount));
      if (typeof mount !== 'function') throw new Error('missing mount');
      var handle = mount(host, ctx()) || {};
      mounted[id] = handle;
      host.__gobViewPending = null;
      return handle;
    }).catch(function () {
      host.__gobViewPending = null;
      delete mounted[id];
      errorCard(host, function () {
        attempts[id] = (attempts[id] || 0) + 1;
        show(id);
      });
    });
    host.__gobViewPending = pending;
    return pending;
  }

  function unmount(id) {
    var handle = mounted[id];
    if (handle && typeof handle.unmount === 'function') handle.unmount();
    delete mounted[id];
    var host = panel(id);
    if (host) {
      host.__gobViewPending = null;
      host.innerHTML = '';
    }
  }

  register({
    id: 'rankings-view',
    section: 'league',
    subtab: 'rankings-view',
    title: 'Rankings',
    module: function (attempt) {
      var href = '/js/shared/views/rankingsView.js';
      if (attempt) href += '?retry=' + attempt;
      return import(href);
    }
  });

  global.GOBViews = {
    register: register,
    has: has,
    show: show,
    unmount: unmount
  };
})(typeof window !== 'undefined' ? window : this);
