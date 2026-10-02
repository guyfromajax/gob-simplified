/**
 * Client player for the server-owned Office moment queue (UX_System §10).
 * MILESTONE kinds use MilestoneModal. Championship + season_review use SeasonPeak
 * (one title takeover for every championship in the visit, then the review).
 * WEEKLY kinds stay cards.
 */
(function (global) {
  'use strict';

  var MILESTONE_KINDS = {
    signed_class: 1,
    walk_on_welcome: 1,
    bracket_reveal: 1,
    region_bye: 1,
    conference_rs_region: 1,
    first_archetype: 1,
    elimination: 1
  };

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

  // The command-center payload carries no franchise_id and the page's own
  // `franchiseId` is a script-scoped binding, not a window property. Without the
  // context read every consume / seen write was skipped and the moment replayed
  // on each Office visit.
  function franchiseIdOf(topData) {
    var fid = (topData && topData.franchise_id) || global.franchiseId || '';
    if (!fid && global.FranchiseContext) {
      try { fid = global.FranchiseContext.franchiseId || ''; } catch (e) { fid = ''; }
    }
    return fid ? String(fid) : '';
  }

  function payload(topData, moment) {
    var ref = moment && moment.payload_ref;
    if (!ref || !topData) return null;
    return topData[ref];
  }

  function patchJson(path, body) {
    var url = path;
    var headers = { 'Content-Type': 'application/json' };
    try {
      if (global.API_CONFIG && typeof global.API_CONFIG.buildUrl === 'function') {
        url = global.API_CONFIG.buildUrl(path);
      }
      if (global.API_CONFIG && typeof global.API_CONFIG.getAuthHeaders === 'function') {
        Object.assign(headers, global.API_CONFIG.getAuthHeaders());
      }
    } catch (e) { /* same-origin fallback */ }
    return fetch(url, {
      method: 'PATCH',
      headers: headers,
      credentials: 'include',
      keepalive: true,
      body: JSON.stringify(body || {})
    }).catch(function () {});
  }

  function markMilestoneSeen(kind, franchiseId, data) {
    if (kind === 'first_archetype') {
      try {
        if (global.__gobAuthMeData) global.__gobAuthMeData.archetype_reveal_seen = true;
      } catch (e) { /* ignore */ }
      // Offline the flag is saved on this computer: /api/auth is always remote
      // and the offline build cannot reach it, so the reveal used to come back
      // on every Office visit. Online is unchanged.
      if (global.GOB_BUILD_PROFILE === 'desktop') {
        if (!franchiseId) return Promise.resolve();
        return patchJson('/franchise/archetype-reveal-seen', { franchise_id: franchiseId });
      }
      return patchJson('/api/auth/archetype-reveal-seen', {});
    }
    if (!franchiseId) return Promise.resolve();
    if (kind === 'conference_rs_region') {
      return patchJson('/franchise/conference-rs-region-modal-seen', { franchise_id: franchiseId });
    }
    if (kind === 'region_bye') {
      return patchJson('/franchise/region-bye-modal-seen', { franchise_id: franchiseId });
    }
    if (kind === 'walk_on_welcome') {
      return patchJson('/franchise/walk-on-welcome-modal-seen', { franchise_id: franchiseId });
    }
    if (kind === 'bracket_reveal') {
      var key = data && data.reveal_key;
      if (!key) return Promise.resolve();
      return patchJson('/franchise/bracket-reveal-modal-seen', { franchise_id: franchiseId, reveal_key: key });
    }
    if (kind === 'signed_class') {
      return patchJson('/franchise/recruiting-results-modal-seen', { franchise_id: franchiseId });
    }
    if (kind === 'elimination') {
      return patchJson('/franchise/elimination-seen', { franchise_id: franchiseId });
    }
    if (kind === 'season_review') {
      return patchJson('/franchise/season-review-seen', { franchise_id: franchiseId });
    }
    return Promise.resolve();
  }

  function openChampionship(topData, moment, ctx) {
    var list = payload(topData, moment);
    if (!Array.isArray(list) || !list.length || !global.ChampionshipMoments) {
      return Promise.resolve();
    }
    var listAll = ctx.list || [];
    var next = listAll[(ctx.queue && ctx.queue.index) || 1];
    return global.ChampionshipMoments.processPendingMoments(
      franchiseIdOf(topData),
      list,
      {
        boxScoreUrlBuilder: ctx.boxScoreUrlBuilder,
        queue: ctx.queue,
        item: moment,
        nextKind: next && next.kind,
      }
    );
  }

  function championshipsFromVisit(topData, list) {
    var out = [];
    (list || []).forEach(function (m) {
      if (!m || m.kind !== 'championship') return;
      var p = payload(topData, m);
      if (Array.isArray(p)) out = out.concat(p);
    });
    return out;
  }

  function openSeasonReview(topData, moment, ctx) {
    if (!global.SeasonPeak || typeof global.SeasonPeak.showReview !== 'function') {
      return Promise.resolve();
    }
    var data = payload(topData, moment);
    if (!data || data.eligible === false) return Promise.resolve();
    var fid = franchiseIdOf(topData);
    var champs = championshipsFromVisit(topData, ctx.list);
    var color = '';
    champs.forEach(function (m) {
      if (!color && m && m.winner_primary_color) color = m.winner_primary_color;
    });
    var seen = markMilestoneSeen('season_review', fid, data);
    return global.SeasonPeak.showReview({
      payload: data,
      titleTrophies: data.titles || [],
      titleMoments: champs,
      item: moment,
      queue: ctx.queue,
      teamName: (topData && (topData.team || topData.user_team_name)) || '',
      teamColor: color,
      season: data.season || (topData && (topData.season || topData.current_season))
    }).then(function () {
      return Promise.resolve(seen);
    });
  }

  function openBigNews(kind, topData, moment, ctx) {
    var data = payload(topData, moment);
    if (!data || !data.eligible || !global.BigNewsModals) return Promise.resolve();
    var maps = ctx.maps || {};
    if (kind === 'bracket_update' && global.BigNewsModals.showBracketUpdate) {
      return global.BigNewsModals.showBracketUpdate(data, topData, maps, ctx.queue);
    }
    return Promise.resolve();
  }

  function openSammy(kind, topData, moment, ctx) {
    var hosts = {
      recruit_visit: global.RecruitVisitModal,
    };
    var host = hosts[kind];
    if (!host || typeof host.showFromQueue !== 'function') return Promise.resolve();
    return host.showFromQueue(topData, ctx.queue);
  }

  function openArchetype(topData, moment, ctx) {
    var key = topData && topData.archetype_evolution_pending;
    if (!key && moment) {
      key = moment.seen_key === 'archetype_evolution_pending'
        ? (topData && topData.archetype_evolution_pending)
        : '';
    }
    if (!key && global.__gobAuthMeData) key = global.__gobAuthMeData.archetype_evolution_pending;
    if (!key || !global.ArchetypeEvolutionModal || !global.ArchetypeEvolutionModal.showFromQueue) {
      return Promise.resolve();
    }
    return global.ArchetypeEvolutionModal.showFromQueue(key, ctx.queue);
  }

  function openMilestone(topData, moment, ctx) {
    if (!global.MilestoneModal || typeof global.MilestoneModal.show !== 'function') {
      return Promise.resolve();
    }
    var data = payload(topData, moment);
    var queue = ctx.queue || {};
    var list = ctx.list || [];
    var index = queue.index || 1;
    var next = list[index];
    var fid = franchiseIdOf(topData);
    var seen = markMilestoneSeen(moment.kind, fid, data);
    return global.MilestoneModal.show({
      item: moment,
      payload: data,
      maps: ctx.maps || {},
      index: index,
      total: queue.total || 1,
      nextKind: next && next.kind,
      nextTitle: next && (next.title || next.kind),
      isLast: index >= (queue.total || list.length)
    }).then(function (reason) {
      return Promise.resolve(seen).then(function () {
        return reason;
      });
    });
  }

  function openOne(topData, moment, ctx) {
    var kind = moment && moment.kind;
    if (kind === 'championship') return openChampionship(topData, moment, ctx);
    if (kind === 'season_review') return openSeasonReview(topData, moment, ctx);
    if (MILESTONE_KINDS[kind]) return openMilestone(topData, moment, ctx);
    if (kind === 'bracket_update') return openBigNews(kind, topData, moment, ctx);
    if (kind === 'archetype_evolution') return openArchetype(topData, moment, ctx);
    return openSammy(kind, topData, moment, ctx);
  }

  // Offline only. "Coaching archetype evolved" is a weekly-card row, not a pop-up,
  // so nothing in the queue marks it. Once the Office has shown it (this is the
  // authoritative read, and the Office is the panel on screen) the pending key is
  // cleared on this computer, so the row shows once. Online is unchanged.
  function clearShownEvolutionRow(topData) {
    if (global.GOB_BUILD_PROFILE !== 'desktop') return;
    var items = Array.isArray(topData && topData.weekly_card_items) ? topData.weekly_card_items : [];
    var listed = items.some(function (item) { return item && item.kind === 'archetype_evolution'; });
    if (!listed) return;
    var office = global.document && global.document.getElementById('office-root');
    if (!office || !office.getClientRects().length) return;
    var franchiseId = franchiseIdOf(topData);
    if (!franchiseId) return;
    patchJson('/franchise/archetype-evolution-seen', { franchise_id: franchiseId });
  }

  function play(topData, opts) {
    opts = opts || {};
    clearShownEvolutionRow(topData);
    var list = Array.isArray(topData && topData.moments_for_this_visit)
      ? topData.moments_for_this_visit
      : [];
    var aborted = false;
    var run = Promise.resolve();
    list.forEach(function (moment, i) {
      run = run.then(function () {
        if (aborted) return;
        return Promise.resolve(openOne(topData, moment, {
          maps: opts.maps,
          boxScoreUrlBuilder: opts.boxScoreUrlBuilder,
          queue: { index: i + 1, total: list.length },
          list: list,
        })).then(function (reason) {
          if (reason === 'dismiss') aborted = true;
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
