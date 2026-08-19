/** Conference regular-season champion's Region Tournament qualification notice. */
(function () {
  'use strict';

  var presented = false;
  var retryTimer = null;
  var retries = 0;
  var MAX_RETRIES = 300;

  function blockerVisible() {
    return Boolean(document.querySelector(
      '.cm-overlay.is-visible,'
      + '.arch-reveal-overlay.is-visible,'
      + '.afm-overlay.is-visible,'
      + '.gob-talert-overlay,'
      + '.sammy-modal-backdrop.open,'
      + '.bn-overlay.show'
    ));
  }

  function franchiseId() {
    return window.franchiseId || new URLSearchParams(window.location.search).get('franchise_id');
  }

  function markSeen(fid) {
    if (!fid || typeof API_CONFIG === 'undefined') return Promise.resolve();
    return fetch(API_CONFIG.buildUrl('/franchise/conference-rs-region-modal-seen'), {
      method: 'PATCH',
      headers: Object.assign(
        { 'Content-Type': 'application/json' },
        API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}
      ),
      body: JSON.stringify({ franchise_id: fid }),
    }).catch(function (err) {
      console.warn('[ConferenceRsRegionModal] could not persist seen state:', err);
    });
  }

  function schedule(data) {
    if (retryTimer || retries >= MAX_RETRIES) return;
    retryTimer = setTimeout(function () {
      retryTimer = null;
      retries += 1;
      maybeShow(data);
    }, 1000);
  }

  function goToLockerRoom() {
    var card = document.getElementById('home-locker-room-body');
    if (!card) return;
    var homeTab = document.querySelector('[data-tab="home-tab"]');
    var homePanel = document.getElementById('home-tab');
    if (homeTab && homePanel && !homePanel.classList.contains('active')) homeTab.click();
    card.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'center',
    });
  }

  function maybeShow(data) {
    var payload = data && data.conference_rs_region_modal;
    if (presented || !payload || !payload.eligible) return;
    if (blockerVisible()) {
      schedule(data);
      return;
    }
    presented = true;
    Promise.all([
      import('/js/shared/sammyModal.js'),
      import('/js/shared/teamCoachAsset.js'),
    ]).then(function (loaded) {
      // A synchronous FCC modal may have opened while the modules loaded.
      if (blockerVisible()) {
        presented = false;
        schedule(data);
        return null;
      }
      var finalSentence = payload.lost_round === 'final'
        ? "Let's go on to the Region Tourney now!"
        : "Let's sim the rest of the Conference Tourney, then get ready for the Region Tourney!";
      loaded[0].showSammyModal({
        eyebrow: 'Region Tournament Qualified',
        body: 'Hey Coach, we lost the game, but because you won the regular-season conference title, you still qualify for the Region Tournament. ' + finalSentence,
        ctaLabel: 'Go To Locker Room',
        imageSrc: loaded[1].getTeamSammyImage(data.team || ''),
        primaryClass: 'is-orange',
        onCta: goToLockerRoom,
      });
      return markSeen(franchiseId());
    }).catch(function (err) {
      console.error('[ConferenceRsRegionModal] failed to show:', err);
    });
  }

  window.ConferenceRsRegionModal = { maybeShow: maybeShow };
})();
