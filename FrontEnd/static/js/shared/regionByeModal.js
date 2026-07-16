/**
 * Week-30 regional-bye Sammy modal.
 *
 * Eligibility and once-per-season persistence are server-authoritative through
 * command-center data and /franchise/region-bye-modal-seen.
 */
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

  function markSeen(franchiseId) {
    if (!franchiseId || typeof API_CONFIG === 'undefined') return Promise.resolve();
    return fetch(API_CONFIG.buildUrl('/franchise/region-bye-modal-seen'), {
      method: 'PATCH',
      headers: Object.assign(
        { 'Content-Type': 'application/json' },
        API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}
      ),
      body: JSON.stringify({ franchise_id: franchiseId }),
    }).catch(function (err) {
      console.warn('[RegionByeModal] could not persist seen state:', err);
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

  function maybeShow(data) {
    if (presented || !data || !data.region_bye_modal_eligible) return;
    if (blockerVisible()) {
      schedule(data);
      return;
    }

    presented = true;
    var franchiseId = window.franchiseId || new URLSearchParams(window.location.search).get('franchise_id');

    Promise.all([
      import('/js/shared/sammyModal.js'),
      import('/js/shared/teamCoachAsset.js'),
    ]).then(function (loaded) {
      var showSammyModal = loaded[0].showSammyModal;
      var getTeamSammyImage = loaded[1].getTeamSammyImage;
      showSammyModal({
        eyebrow: 'Region Tournament Bye',
        body: 'Hey Coach, congratulations! You won both your conference regular-season title and your conference tournament title. This means you\u2019ve earned a bye in the Region Tournament and have automatically qualified for the Region Championship game. Sim this week\u2019s games, then start preparing for the Region Championship!',
        ctaLabel: 'Sim Region First Round',
        secondaryLabel: 'Back to Locker Room',
        imageSrc: getTeamSammyImage(data.team || ''),
        onCta: function () {
          var playButton = document.getElementById('play-now');
          if (!playButton || playButton.dataset.mode !== 'sim-rest-tournament') {
            throw new Error('Region first-round simulation is not available.');
          }
          playButton.click();
        },
        onSecondary: function () {},
      });
      return markSeen(franchiseId);
    }).catch(function (err) {
      console.error('[RegionByeModal] failed to show:', err);
    });
  }

  window.RegionByeModal = { maybeShow: maybeShow };
})();
