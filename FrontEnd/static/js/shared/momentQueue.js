/**
 * Office moment queue. The server picks order and the 1–2 cap.
 * This file only opens the existing modal for each kind in that list.
 */
(function (global) {
  'use strict';

  var settled = Promise.resolve();
  var settleWaiters = [];

  function queueLabel(ctx, eyebrow) {
    var total = ctx && ctx.total;
    var index = ctx && ctx.index;
    if (!total || total < 2 || !index) return eyebrow || '';
    var prefix = index + ' of ' + total;
    return eyebrow ? prefix + ' · ' + eyebrow : prefix;
  }

  function notifySettled() {
    var waiters = settleWaiters.slice();
    settleWaiters = [];
    waiters.forEach(function (fn) {
      try { fn(); } catch (err) {}
    });
  }

  function whenSettled(fn) {
    if (typeof fn !== 'function') return;
    settled.then(function () { fn(); }, function () { fn(); });
  }

  function payload(topData, moment) {
    var ref = moment && moment.payload_ref;
    if (!ref || !topData) return null;
    return topData[ref];
  }

  function openChampionship(topData, moment, ctx) {
    var list = payload(topData, moment);
    if (!Array.isArray(list) || !list.length || !global.ChampionshipMoments) {
      return Promise.resolve();
    }
    return global.ChampionshipMoments.processPendingMoments(
      global.franchiseId,
      list,
      {
        boxScoreUrlBuilder: ctx.boxScoreUrlBuilder,
        queueLabel: queueLabel(ctx.queue, 'Championship'),
      }
    );
  }

  function openBigNews(kind, topData, moment, ctx) {
    var data = payload(topData, moment);
    if (!data || !data.eligible || !global.BigNewsModals) return Promise.resolve();
    var maps = ctx.maps || {};
    if (kind === 'bracket_reveal' && global.BigNewsModals.showBracketReveal) {
      return global.BigNewsModals.showBracketReveal(data, topData, maps, ctx.queue);
    }
    if (kind === 'bracket_update' && global.BigNewsModals.showBracketUpdate) {
      return global.BigNewsModals.showBracketUpdate(data, topData, maps, ctx.queue);
    }
    return Promise.resolve();
  }

  function openSammy(kind, topData, moment, ctx) {
    var hosts = {
      conference_rs_region: global.ConferenceRsRegionModal,
      region_bye: global.RegionByeModal,
      walk_on_welcome: global.WalkOnWelcomeModal,
      recruit_visit: global.RecruitVisitModal,
    };
    var host = hosts[kind];
    if (!host || typeof host.showFromQueue !== 'function') return Promise.resolve();
    return host.showFromQueue(topData, ctx.queue);
  }

  function openArchetype(topData, moment, ctx) {
    var key = topData && topData.archetype_evolution_pending;
    if (!key && moment) key = moment.seen_key === 'archetype_evolution_pending' ? (topData && topData.archetype_evolution_pending) : '';
    if (!key && global.__gobAuthMeData) key = global.__gobAuthMeData.archetype_evolution_pending;
    if (!key || !global.ArchetypeEvolutionModal || !global.ArchetypeEvolutionModal.showFromQueue) {
      return Promise.resolve();
    }
    return global.ArchetypeEvolutionModal.showFromQueue(key, ctx.queue);
  }

  function openOne(topData, moment, ctx) {
    var kind = moment && moment.kind;
    if (kind === 'championship') return openChampionship(topData, moment, ctx);
    if (kind === 'bracket_reveal' || kind === 'bracket_update') {
      return openBigNews(kind, topData, moment, ctx);
    }
    if (kind === 'archetype_evolution') return openArchetype(topData, moment, ctx);
    return openSammy(kind, topData, moment, ctx);
  }

  function play(topData, opts) {
    opts = opts || {};
    var list = Array.isArray(topData && topData.moments_for_this_visit)
      ? topData.moments_for_this_visit
      : [];
    var run = Promise.resolve();
    list.forEach(function (moment, i) {
      run = run.then(function () {
        return openOne(topData, moment, {
          maps: opts.maps,
          boxScoreUrlBuilder: opts.boxScoreUrlBuilder,
          queue: { index: i + 1, total: list.length },
        });
      });
    });
    settled = run.then(notifySettled, notifySettled);
    return settled;
  }

  global.MomentQueue = {
    play: play,
    whenSettled: whenSettled,
    queueLabel: queueLabel,
  };
})(typeof window !== 'undefined' ? window : this);
