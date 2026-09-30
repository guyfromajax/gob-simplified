/**
 * Trophy Case — standalone page (Home Base chrome, outside the franchise shell).
 * One GET: /franchise/coach-career (loopback on desktop). No community/auth calls.
 */
(function (global) {
  'use strict';

  var TITLE_KINDS = {
    national: { letter: 'N', label: 'National Champions' },
    region: { letter: 'R', label: 'Region Champions' },
    conf_t: { letter: 'C', label: 'Conference Champions' },
    conf_rs: { letter: 'C', label: 'Conference Regular-Season #1' }
  };
  var MILESTONE_KINDS = {
    milestone_first_signing_class: { letter: 'S', label: 'First signing class' },
    milestone_first_bracket: { letter: 'B', label: 'First bracket' },
    milestone_first_archetype: { letter: 'A', label: 'First coach archetype' }
  };

  var root = document.getElementById('trophy-case');
  var career = null;
  var reviewOpen = false;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function isDesktop() {
    if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.getBuildProfile === 'function') {
      return API_CONFIG.getBuildProfile() === 'desktop';
    }
    return global.GOB_BUILD_PROFILE === 'desktop';
  }

  function authHeaders() {
    try {
      if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.getAuthHeaders === 'function') {
        return API_CONFIG.getAuthHeaders() || {};
      }
    } catch (e) { /* ignore */ }
    return {};
  }

  function careerUrl() {
    if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.buildUrl === 'function') {
      return API_CONFIG.buildUrl('/franchise/coach-career');
    }
    return '/franchise/coach-career';
  }

  function hideLoader() {
    var overlay = document.getElementById('page-load-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  function topBarHtml(data) {
    var online = !isDesktop();
    var name = (data && data.username) || 'Coach';
    var conn = online
      ? '<span class="hb-conn"><i></i>Online</span>'
      : '<span class="hb-conn off"><i></i>Offline · saves on this computer</span>';
    var out = online
      ? '<button type="button" class="hb-tl" data-tc-logout data-sfx="SFX_SELECT">Log Out</button>'
      : '';
    return '<header class="hb-top">'
      + '<div class="hb-mark"><b>Geeked-Out Basketball</b><span>Home Base</span></div>'
      + '<a class="up" href="/mode-select.html" data-sfx="SFX_SELECT">'
      + '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M10 3 5 8l5 5"/></svg>'
      + 'Home Base</a>'
      + '<div class="hb-sp"></div>'
      + '<div class="hb-acct">' + conn + '<b>' + esc(name) + '</b>' + out + '</div>'
      + '</header>';
  }

  function cn(value, label, zero) {
    return '<div class="cn' + (zero ? ' z' : '') + '"><b>' + esc(value) + '</b><span>' + esc(label) + '</span></div>';
  }

  function trophiesOf(kinds) {
    return ((career && career.trophies) || []).filter(function (t) {
      return t && kinds[t.kind];
    });
  }

  function titlesShelf(titles) {
    if (!titles.length) {
      return '<div class="shelf is-empty"><span class="med open lg"></span><span class="med open lg"></span><span class="med open lg"></span>'
        + '<p>Win your conference, your region or the national tournament. The title is kept here for good.</p></div>';
    }
    return '<div class="shelf">' + titles.map(function (t) {
      var spec = TITLE_KINDS[t.kind];
      var sub = [t.team_name, t.season != null ? 'Season ' + t.season : ''].filter(Boolean).join(' · ');
      return '<div class="tro"><span class="med gold lg">' + esc(spec.letter) + '</span>'
        + '<div><b>' + esc(spec.label) + '</b>' + (sub ? '<span>' + esc(sub) + '</span>' : '') + '</div></div>';
    }).join('') + '</div>';
  }

  function milestoneShelf(miles) {
    if (!miles.length) {
      return '<div class="tc-empty">Firsts land here: your first signing class, first bracket, first coach archetype.</div>';
    }
    return '<div class="shelf">' + miles.map(function (t) {
      var spec = MILESTONE_KINDS[t.kind];
      var sub = [t.team_name, t.season != null ? 'Season ' + t.season : ''].filter(Boolean).join(' · ');
      if (t.kind === 'milestone_first_archetype') sub = 'Coach archetype';
      return '<div class="tro sm"><span class="med ms">' + esc(spec.letter) + '</span>'
        + '<div><b>' + esc(spec.label) + '</b>' + (sub ? '<span>' + esc(sub) + '</span>' : '') + '</div></div>';
    }).join('') + '</div>';
  }

  function finishForRecord(record, titles) {
    if (record.finish) return record.finish;
    if (record.in_progress && record.week != null) return 'In progress · Week ' + record.week;
    var kinds = {};
    (titles || []).forEach(function (t) {
      if (t.season === record.season && t.team_name === record.team_name) kinds[t.kind] = 1;
    });
    var order = ['national', 'region', 'conf_t', 'conf_rs'];
    var i;
    for (i = 0; i < order.length; i++) {
      if (kinds[order[i]]) return TITLE_KINDS[order[i]].label;
    }
    return '';
  }

  function reviewRows() {
    var titles = trophiesOf(TITLE_KINDS);
    var records = ((career && career.trophies) || []).filter(function (t) {
      return t && t.kind === 'season_record';
    });
    var tops = (career && career.top_seasons) || [];
    var seen = {};
    var rows = [];

    records.forEach(function (t) {
      var d = t.detail && typeof t.detail === 'object' ? t.detail : {};
      var key = String(t.franchise_id || '') + ':' + String(t.season || '');
      seen[key] = 1;
      rows.push({
        season: t.season,
        program: t.team_name || d.program || '',
        wins: d.wins,
        losses: d.losses,
        finish: finishForRecord({
          season: t.season, team_name: t.team_name, finish: d.finish
        }, titles),
        reviewable: true,
        trophy: t
      });
    });

    tops.forEach(function (s) {
      var key = String(s.franchise_id || '') + ':' + String(s.season || '');
      if (seen[key]) return;
      rows.push({
        season: s.season,
        program: s.team_name || '',
        wins: s.wins,
        losses: s.losses,
        finish: s.in_progress && s.week != null
          ? 'In progress · Week ' + s.week
          : (s.finish || ''),
        reviewable: false
      });
    });

    rows.sort(function (a, b) {
      return (Number(b.season) || 0) - (Number(a.season) || 0);
    });
    return rows;
  }

  function reviewsTable(rows) {
    if (!rows.length) {
      return '<div class="tc-empty"><b>No season reviews yet</b>Your first review is written when a season ends: record, titles, awards, best players and the class you signed.</div>';
    }
    return '<div class="tcard"><table class="tbl"><thead><tr>'
      + '<th class="l">Season</th><th class="l w">Program</th><th>Record</th><th class="l">Finish</th><th></th>'
      + '</tr></thead><tbody>'
      + rows.map(function (r, i) {
        var rec = (r.wins != null && r.losses != null) ? (r.wins + '–' + r.losses) : '';
        var action = r.reviewable
          ? '<button type="button" class="lnk" data-tc-review="' + i + '" data-sfx="SFX_SELECT">Review</button>'
          : '<span class="qt">—</span>';
        return '<tr><td class="l b">' + (r.season != null ? 'Season ' + esc(r.season) : '') + '</td>'
          + '<td class="l w">' + esc(r.program) + '</td>'
          + '<td class="b">' + esc(rec) + '</td>'
          + '<td class="l dim">' + esc(r.finish) + '</td>'
          + '<td>' + action + '</td></tr>';
      }).join('')
      + '</tbody></table></div>';
  }

  function render() {
    if (!root || !career) return;
    var record = career.record || {};
    var wins = Number(record.wins) || 0;
    var losses = Number(record.losses) || 0;
    var titlesN = Number(career.titles_total) || 0;
    var seasonsN = Number(career.seasons_completed) || 0;
    var programsN = Number(career.programs) || 0;
    var titles = trophiesOf(TITLE_KINDS);
    var miles = trophiesOf(MILESTONE_KINDS);
    var rows = reviewRows();
    root.innerHTML = '<div class="hb">' + topBarHtml(career)
      + '<main class="tc">'
      + '<div class="tc-head"><h1><small>Coach career · all programs</small>Trophy Case</h1>'
      + cn(wins + '–' + losses, 'Record', wins + losses === 0)
      + cn(String(titlesN), 'Titles', titlesN === 0)
      + cn(String(seasonsN), 'Seasons', seasonsN === 0)
      + cn(String(programsN), 'Programs', programsN === 0)
      + '</div>'
      + '<div class="tc-col">'
      + '<div class="sec"><div class="sec-h"><h3>Titles</h3>'
      + (titles.length ? '<span>' + titles.length + '</span>' : '') + '</div></div>'
      + titlesShelf(titles)
      + '<div class="sec"><div class="sec-h"><h3>Milestones</h3>'
      + (miles.length ? '<span>' + miles.length + '</span>' : '') + '</div></div>'
      + milestoneShelf(miles)
      + '</div>'
      + '<div class="tc-col">'
      + '<div class="sec"><div class="sec-h"><h3>Season Reviews</h3><span>Every season, every program</span></div></div>'
      + reviewsTable(rows)
      + '</div></main></div>';

    root.querySelectorAll('[data-tc-review]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = Number(btn.getAttribute('data-tc-review'));
        openStoredReview(rows[idx]);
      });
    });
    var logout = root.querySelector('[data-tc-logout]');
    if (logout) {
      logout.addEventListener('click', function () {
        try { localStorage.removeItem('auth_token'); localStorage.removeItem('auth_user'); } catch (e) { /* ignore */ }
        if (global.GOBNav && typeof global.GOBNav.go === 'function') global.GOBNav.go('/login.html');
        else global.location.href = '/login.html';
      });
    }
  }

  function openStoredReview(row) {
    if (!row || !row.reviewable || !global.SeasonPeak) return;
    if (reviewOpen) return;
    reviewOpen = true;
    var detail = (row.trophy && row.trophy.detail) || {};
    var payload = Object.assign({}, detail, {
      season: row.season,
      program: row.program,
      team_name: row.program
    });
    // Region seed is omitted even when a stored snapshot still has it.
    delete payload.region_seed;
    var titleTrophies = trophiesOf(TITLE_KINDS).filter(function (t) {
      return t.season === row.season && (!row.program || t.team_name === row.program);
    });
    Promise.resolve(global.SeasonPeak.showReview({
      payload: payload,
      titleTrophies: titleTrophies,
      teamName: row.program,
      season: row.season,
      readonly: true
    })).then(function () {
      reviewOpen = false;
    }, function () {
      reviewOpen = false;
    });
  }

  function load() {
    return fetch(careerUrl(), {
      credentials: 'same-origin',
      headers: authHeaders()
    }).then(function (res) {
      if (!res.ok) throw new Error('coach-career ' + res.status);
      return res.json();
    }).then(function (data) {
      career = data || {};
      render();
      hideLoader();
    }).catch(function () {
      career = {
        username: 'Coach',
        record: { wins: 0, losses: 0 },
        titles_total: 0,
        seasons_completed: 0,
        programs: 0,
        trophies: [],
        top_seasons: []
      };
      render();
      hideLoader();
    });
  }

  if (root) load();
})(typeof window !== 'undefined' ? window : this);
