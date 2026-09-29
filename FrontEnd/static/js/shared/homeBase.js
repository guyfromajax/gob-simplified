/**
 * Home Base — the pre-franchise hub that replaces the mode-select layout.
 *
 * This module owns the DOM and the interaction (slots, slot menu, delete
 * confirm, the Around GOB / Leaderboard tab panel, keyboard). It owns no data:
 * mode-select.js loads the payloads, applies the green rule, and hands down a
 * view model. Navigation, delete and logout come back through the callbacks in
 * `init`.
 *
 * Colour law: exactly one `.advance` per screen, on the program the green rule
 * picks. Navy marks "yours". Nothing here is orange or reward gold.
 */
(function (global) {
  'use strict';

  var TAB_STORAGE_KEY = 'gob_hb_tab';
  var TABS = ['ag', 'lb'];
  /** 1920 shows 4×3; 1280 hides the 7th cell on, so one list serves both. */
  var GRID_CELLS = 12;

  var handlers = {};
  var root = null;
  var surface = null;
  var lastView = {};
  var activeTab = 'ag';
  var openMenuSlot = null;
  var confirmReturnFocus = null;

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function readTab() {
    try {
      var raw = global.localStorage && global.localStorage.getItem(TAB_STORAGE_KEY);
      return TABS.indexOf(raw) >= 0 ? raw : 'ag';
    } catch (_err) {
      return 'ag';
    }
  }

  function writeTab(tab) {
    try {
      if (global.localStorage) global.localStorage.setItem(TAB_STORAGE_KEY, tab);
    } catch (_err) { /* private mode */ }
  }

  // ── Top bar ──────────────────────────────────────────────
  function topBarHtml(view) {
    var online = !!view.online;
    var conn = online
      ? '<span class="hb-conn"><i></i>Online</span>'
      : '<span class="hb-conn off"><i></i>Offline · saves on this computer</span>';
    var acct = '<b>' + esc(view.accountName || 'Coach') + '</b>';
    var out = online
      ? '<button type="button" class="hb-tl" data-hb-logout data-sfx="SFX_SELECT">Log Out</button>'
      : '';
    return '<header class="hb-top">'
      + '<div class="hb-mark"><b>Geeked-Out Basketball</b><span>Home Base</span></div>'
      + '<div class="hb-sp"></div>'
      + '<div class="hb-acct">' + conn + acct + out + '</div>'
      + '</header>';
  }

  // ── Left zone: program slots ─────────────────────────────
  function doorHtml(slot) {
    var green = !!slot.isGreen;
    var live = !!slot.gameInProgress;
    var label = live ? 'Resume Game' : 'Enter';
    var btnClass = green ? 'advance' : 'btn-ghost sm';
    var art = slot.bannerUrl
      ? '<img src="' + esc(slot.bannerUrl) + '" alt="">'
      : '';
    var tag = slot.isLastPlayed ? '<span class="door-tag">Last played</span>' : '';
    // The strip carries the week only. Score and quarter stay off the door.
    var liveStrip = live
      ? '<div class="door-live"><i></i>Game in progress <span>· Week ' + esc(slot.week) + '</span></div>'
      : '';
    var meta2 = slot.nextOpponent
      ? '<div class="door-m tight">' + (live ? 'In game' : 'Next') + ' <i>·</i>' + esc(slot.nextOpponent) + '</div>'
      : '';
    var nums = '';
    if (slot.record) nums += '<div><b>' + esc(slot.record) + '</b><span>Record</span></div>';
    if (slot.rank) nums += '<div><b>' + esc(slot.rank) + '</b><span>National</span></div>';

    return '<div class="door" role="link" tabindex="0"'
      + ' data-hb-door data-franchise-id="' + esc(slot.franchiseId) + '"'
      + ' aria-label="' + esc((live ? 'Resume game · ' : 'Enter ') + slot.name) + '">'
      + '<div class="door-art">' + art + tag + liveStrip + '</div>'
      + '<div class="door-i">'
      + '<div class="door-id">'
      + '<div class="door-n">' + esc(slot.name) + '</div>'
      + '<div class="door-m">Season ' + esc(slot.season) + '<i>·</i>Week ' + esc(slot.week) + '</div>'
      + meta2
      + '</div>'
      + (nums ? '<div class="door-nums">' + nums + '</div>' : '<div></div>')
      + '<button type="button" class="' + btnClass + '" data-hb-enter'
      + ' data-franchise-id="' + esc(slot.franchiseId) + '"'
      + ' data-sfx="' + (green ? 'SFX_ADVANCE' : 'SFX_SELECT') + '">' + esc(label) + '</button>'
      + '</div>'
      + '</div>';
  }

  function vacantHtml(anyProgram, slotIndex) {
    // Existing copy. The helper line under it is the only new string.
    var title = anyProgram ? 'Start Another Franchise' : 'Start Your Coaching Journey';
    var help = anyProgram
      ? 'Slot ' + slotIndex + ' is open. Take over another program, or build your own.'
      : 'Take over one of 128 programs, or build your own in Team Builder.';
    return '<div class="vacant">'
      + '<b>' + esc(title) + '</b>'
      + '<p>' + esc(help) + '</p>'
      + '<button type="button" class="btn-ghost sm" data-hb-new-franchise data-slot="' + esc(slotIndex)
      + '" data-sfx="SFX_SELECT">Find Your Program</button>'
      + '</div>';
  }

  function slotsHtml(view) {
    var slots = view.slots || [];
    var any = slots.some(function (s) { return !!s; });
    var html = '';
    for (var i = 0; i < slots.length; i += 1) {
      var slot = slots[i];
      var n = '0' + (i + 1);
      var more = slot
        ? '<button type="button" class="slot-more" data-hb-more data-slot="' + (i + 1) + '"'
          + ' aria-label="Program options, slot ' + n + '" aria-haspopup="menu" aria-expanded="false">···</button>'
        : '';
      html += '<div class="slot" data-hb-slot="' + (i + 1) + '">'
        + '<div class="slot-h"><b>' + n + '</b><i></i>' + more + '</div>'
        + (slot ? doorHtml(slot) : vacantHtml(any, i + 1))
        + '</div>';
    }
    return html;
  }

  /**
   * Career strip. Every numeral is a server value formatted for display; a
   * field the payload does not carry drops its cell rather than being guessed.
   * A zero renders hollow: potential, not an achievement.
   */
  function careerStripHtml(view) {
    var career = view.career;
    if (!career) return '';
    var cells = '';
    function cell(value, label, zero, aside) {
      cells += '<div><div class="cr-v"><b' + (zero ? ' class="hollow"' : '') + '>' + esc(value) + '</b>'
        + (aside ? '<em>' + esc(aside) + '</em>' : '') + '</div>'
        + '<span>' + esc(label) + '</span></div>';
    }
    if (career.record) {
      // The win % rides the numeral, not the label: the left column is too
      // narrow for "Career record · .768" at the label's tracking.
      cell(career.record, 'Career record', !!career.recordEmpty, career.winPct);
    }
    if (career.titles != null) cell(career.titles, 'Titles', Number(career.titles) === 0);
    if (career.seasons != null) cell(career.seasons, 'Seasons', Number(career.seasons) === 0);
    if (career.geekPoints != null) cell(career.geekPoints, 'Geek Points', Number(career.geekPointsRaw) === 0);
    if (!cells) return '';

    // PR 5 owns the Trophy Case route. Until it lands the entry stays off.
    var trophy = view.trophyCaseHref
      ? '<a class="lnk" href="' + esc(view.trophyCaseHref) + '" data-hb-trophy-case data-sfx="SFX_SELECT">Trophy Case</a>'
      : '';
    return '<div class="hb-career" data-hb-career>'
      + '<div class="cr-n">' + cells + '</div>' + trophy + '</div>';
  }

  function leftHtml(view) {
    var slots = view.slots || [];
    var used = slots.filter(Boolean).length;
    return '<section class="hb-l">'
      + '<div class="hb-h"><h2>Your Programs</h2><span>' + used + ' of ' + slots.length + ' slots</span></div>'
      + '<div class="slots" data-hb-slots>' + slotsHtml(view) + '</div>'
      + careerStripHtml(view)
      + '<div class="hb-util">'
      + '<a class="hb-link go" href="/tutorial.html" data-sfx="SFX_SELECT">Tutorials</a>'
      + '<button type="button" class="hb-link" data-hb-settings data-sfx="SFX_SELECT">Settings</button>'
      + '<a class="hb-link go" href="/faqs.html" data-sfx="SFX_SELECT">FAQs</a>'
      + '</div>'
      + '</section>';
  }

  // ── Right zone: Around GOB ───────────────────────────────
  function agcHtml(card) {
    var art = card.bannerUrl
      ? '<img class="agc-bg" src="' + esc(card.bannerUrl) + '" alt="">'
      : '';
    var artInner = card.bannerUrl
      ? '<img src="' + esc(card.bannerUrl) + '" alt="">'
      : '';
    var who = card.isMe ? 'You' : (card.coach || 'Coach');
    var dot = (card.isNew && !card.isMe) ? '<i></i>' : '';
    // Season + week ride together; either missing drops the pair.
    var when = (card.season != null && card.week != null)
      ? '<small>SN ' + esc(card.season) + '<i>·</i>WK ' + esc(card.week) + '</small>'
      : '';
    var score = card.score ? '<b>' + esc(card.score) + '</b>' : '';
    var verb = card.won ? 'def.' : 'lost to';
    var versus = card.opponent
      ? '<div class="agc-v"><em>' + verb + '</em> <b>' + esc(card.opponent) + '</b></div>'
      : '';
    var metaBits = [];
    if (card.team) metaBits.push(esc(card.team));
    if (card.record) metaBits.push(esc(card.record));
    if (card.rank) metaBits.push(esc(card.rank) + ' national');
    var meta = metaBits.length
      ? '<div class="agc-m">' + metaBits.join('<i>·</i>') + '</div>'
      : '';
    var label = who + ': ' + (card.team || '') + ' ' + (card.won ? 'beat' : 'lost to') + ' '
      + (card.opponent || '') + ' ' + (card.score || '');

    return '<article class="agc' + (card.isMe ? ' is-me' : '') + '" aria-label="' + esc(label.trim()) + '">'
      + art
      + '<div class="agc-art">' + artInner + '<span class="agc-coach">' + dot + esc(who) + '</span></div>'
      + '<div class="agc-b">'
      + '<div class="agc-s"><span class="wl ' + (card.won ? 'w' : 'l') + '">' + (card.won ? 'W' : 'L') + '</span>'
      + score + when + '</div>'
      + versus
      + meta
      + '</div>'
      + '</article>';
  }

  function aroundHtml(cards) {
    var list = (cards || []).slice(0, GRID_CELLS);
    var html = list.map(agcHtml).join('');
    for (var i = list.length; i < GRID_CELLS; i += 1) {
      html += '<article class="agc is-wait" aria-hidden="true">Waiting for next result</article>';
    }
    return '<div class="agc-g" data-hb-grid>' + html + '</div>';
  }

  // ── Right zone: Leaderboard ──────────────────────────────
  function leaderboardHtml(board) {
    var rows = (board && board.rows) || [];
    var tiles = rows.slice(0, 3).map(function (r, i) {
      return '<div class="lbt"><i>' + (i + 1) + '</i><div>'
        + '<b>' + esc(r.name) + '</b>'
        + '<span>' + esc(r.value) + '<small>' + esc(board.unit || 'GP') + '</small></span>'
        + '</div></div>';
    }).join('');

    var listRows = rows.slice(3).map(function (r, i) {
      // .x trims the tail at 1280 if the server ever returns a longer board.
      var trim = i >= 8 ? ' x' : '';
      return '<div class="ldb-r' + (r.isMe ? ' me' : '') + trim + '">'
        + '<span>' + esc(r.rank) + '</span>'
        + '<span class="ldb-n"><span class="nm">' + esc(r.name) + '</span>'
        + (r.isMe ? '<em>You</em>' : '') + '</span>'
        + '<b>' + esc(r.value) + '</b>'
        + '</div>';
    }).join('');

    var pinned = '';
    if (board && board.me && !board.meInTop) {
      pinned = '<div class="ldb-r me">'
        + '<span>' + esc(board.me.rank) + '</span>'
        + '<span class="ldb-n"><span class="nm">' + esc(board.me.name) + '</span><em>You</em></span>'
        + '<b>' + esc(board.me.value) + '</b>'
        + '</div>';
    }

    // The two footer links are navigation, not data: they stay on an empty board.
    var footer = '<div class="sec-f">'
      + '<a class="lnk" href="#" data-hb-by-team data-sfx="SFX_SELECT">By team</a>'
      + '<a class="lnk" href="/coaching-archetypes-leaderboard.html" data-sfx="SFX_SELECT">Coaching archetypes</a>'
      + '</div>';
    if (!rows.length) {
      return '<div class="hb-empty-r">Leaderboard coming soon</div>' + footer;
    }
    return '<div class="lbp">' + tiles + '</div>'
      + '<div class="lbl">' + listRows + pinned + '</div>'
      + footer;
  }

  /** The sub-line for Around GOB; the measure toggle for the Leaderboard. */
  function toolsHtml(tab, view) {
    if (tab === 'ag') return 'Latest results from every coach\u2019s own league';
    var measure = (view.leaderboard && view.leaderboard.view) === 'titles' ? 'titles' : 'geek_points';
    function radio(key, label) {
      var on = measure === key;
      return '<button type="button" role="radio" data-hb-lb-view="' + key + '"'
        + ' aria-checked="' + on + '"' + (on ? ' class="on"' : '')
        + ' data-sfx="SFX_SELECT">' + label + '</button>';
    }
    return '<div class="seg" role="radiogroup" aria-label="Leaderboard measure">'
      + radio('geek_points', 'Geek Points') + radio('titles', 'Titles') + '</div>';
  }

  /** The count rides the Around GOB tab only while the Leaderboard is showing. */
  function pillHtml(tab, view) {
    var newCount = Number(view.newCount) || 0;
    return (tab === 'lb' && newCount > 0) ? '<span class="hbt-n">' + esc(newCount) + '</span>' : '';
  }

  function rightOnlineHtml(view) {
    var tab = activeTab;
    var pill = pillHtml(tab, view);
    var tools = toolsHtml(tab, view);

    return '<section class="hb-r">'
      + '<div class="fag" aria-disabled="true">'
      + '<div class="fag-t"><div class="eyebrow">Head to head · Online only</div>'
      + '<h3>Find A Game</h3><p>Your program against another coach\u2019s program.</p></div>'
      + '<span class="soon"><i></i>Coming Soon</span>'
      + '</div>'
      + '<div class="hbt">'
      + '<div class="hbt-row">'
      + '<div class="hbt-tabs" role="tablist" aria-label="Community">'
      + '<button type="button" class="hbt-tb" role="tab" id="hb-tab-ag" data-hb-tab="ag"'
      + ' aria-controls="hb-panel-ag" aria-selected="' + (tab === 'ag') + '"'
      + ' tabindex="' + (tab === 'ag' ? '0' : '-1') + '" data-sfx="SFX_SELECT">Around GOB' + pill + '</button>'
      + '<button type="button" class="hbt-tb" role="tab" id="hb-tab-lb" data-hb-tab="lb"'
      + ' aria-controls="hb-panel-lb" aria-selected="' + (tab === 'lb') + '"'
      + ' tabindex="' + (tab === 'lb' ? '0' : '-1') + '" data-sfx="SFX_SELECT">Leaderboard</button>'
      + '</div>'
      + '<div class="hbt-tools">' + tools + '</div>'
      + '</div>'
      + '<div class="hbt-p" role="tabpanel" id="hb-panel-ag" aria-labelledby="hb-tab-ag" data-hb-panel="ag"'
      + (tab === 'ag' ? '' : ' hidden') + '>' + aroundHtml(view.around) + '</div>'
      + '<div class="hbt-p" role="tabpanel" id="hb-panel-lb" aria-labelledby="hb-tab-lb" data-hb-panel="lb"'
      + (tab === 'lb' ? '' : ' hidden') + '>' + leaderboardHtml(view.leaderboard) + '</div>'
      + '</div>'
      + '</section>';
  }

  /** Desktop: the zone stays empty until "Your Career" lands. No remote calls. */
  function rightOfflineHtml() {
    return '<section class="hb-r" data-hb-right-offline></section>';
  }

  // ── Render ───────────────────────────────────────────────
  function render(view) {
    if (!surface) return;
    lastView = view || {};
    var right = lastView.online ? rightOnlineHtml(lastView) : rightOfflineHtml();
    surface.innerHTML = '<div class="hb">' + topBarHtml(lastView) + '<main class="hb-body">'
      + leftHtml(lastView) + right + '</main></div>';
    openMenuSlot = null;
  }

  /** Partial updates so polling and the measure toggle do not steal focus. */
  function renderAround(cards, newCount) {
    if (!root) return;
    lastView.around = cards;
    if (newCount != null) lastView.newCount = newCount;
    var panel = root.querySelector('[data-hb-panel="ag"]');
    if (panel) panel.innerHTML = aroundHtml(cards);
    var agTab = root.querySelector('[data-hb-tab="ag"]');
    if (agTab) {
      var oldPill = agTab.querySelector('.hbt-n');
      if (oldPill) oldPill.parentNode.removeChild(oldPill);
      agTab.insertAdjacentHTML('beforeend', pillHtml(activeTab, lastView));
    }
  }

  function renderLeaderboard(board) {
    if (!root) return;
    lastView.leaderboard = board;
    var panel = root.querySelector('[data-hb-panel="lb"]');
    if (panel) panel.innerHTML = leaderboardHtml(board);
    if (activeTab === 'lb') {
      var tools = root.querySelector('.hbt-tools');
      if (tools) tools.innerHTML = toolsHtml('lb', lastView);
    }
  }

  // ── Slot menu ────────────────────────────────────────────
  function closeMenu(restoreFocus) {
    if (!root) return;
    var pop = root.querySelector('.pop');
    if (pop) pop.parentNode.removeChild(pop);
    var btns = root.querySelectorAll('[data-hb-more]');
    Array.prototype.forEach.call(btns, function (b) {
      b.classList.remove('open');
      b.setAttribute('aria-expanded', 'false');
    });
    if (restoreFocus && openMenuSlot) {
      var back = root.querySelector('[data-hb-more][data-slot="' + openMenuSlot + '"]');
      if (back) back.focus();
    }
    openMenuSlot = null;
  }

  function openMenu(btn) {
    var slotIndex = btn.getAttribute('data-slot');
    if (openMenuSlot === slotIndex) { closeMenu(true); return; }
    closeMenu(false);
    var slot = root.querySelector('[data-hb-slot="' + slotIndex + '"]');
    if (!slot) return;
    var pop = document.createElement('div');
    pop.className = 'pop';
    pop.setAttribute('role', 'menu');
    pop.innerHTML = '<button type="button" class="pop-i danger" role="menuitem"'
      + ' data-hb-delete data-slot="' + esc(slotIndex) + '">Delete program…</button>';
    slot.appendChild(pop);
    btn.classList.add('open');
    btn.setAttribute('aria-expanded', 'true');
    openMenuSlot = slotIndex;
    var first = pop.querySelector('.pop-i');
    if (first) first.focus();
  }

  // ── Delete confirm ───────────────────────────────────────
  function confirmHost() {
    return document.getElementById('hb-confirm-host');
  }

  function openConfirm(spec) {
    var host = confirmHost();
    if (!host) return;
    confirmReturnFocus = document.activeElement;
    closeMenu(false);
    host.innerHTML = '<div class="hb-scrim" data-hb-scrim>'
      + '<div class="cfm" role="alertdialog" aria-modal="true" aria-labelledby="hb-cfm-t" aria-describedby="hb-cfm-b">'
      + '<h3 id="hb-cfm-t">' + esc(spec.title) + '</h3>'
      + '<p id="hb-cfm-b">' + spec.bodyHtml + '</p>'
      + '<div class="cfm-f">'
      + '<button type="button" class="btn-ghost sm" data-hb-cancel data-sfx="SFX_SELECT">'
      + esc(spec.cancelLabel || 'Cancel') + '</button>'
      + (spec.confirmLabel
        ? '<button type="button" class="btn-del" data-hb-confirm-delete>' + esc(spec.confirmLabel) + '</button>'
        : '')
      + '</div></div></div>';
    host.hidden = false;
    // Cancel takes default focus: the safe choice on a destructive dialog.
    var cancel = host.querySelector('[data-hb-cancel]');
    if (cancel) cancel.focus();
  }

  function closeConfirm() {
    var host = confirmHost();
    if (!host) return;
    host.innerHTML = '';
    host.hidden = true;
    if (confirmReturnFocus && typeof confirmReturnFocus.focus === 'function'
      && document.contains(confirmReturnFocus)) {
      confirmReturnFocus.focus();
    }
    confirmReturnFocus = null;
  }

  function trapFocus(ev) {
    var host = confirmHost();
    if (!host || host.hidden) return;
    var focusables = host.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (!focusables.length) return;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (ev.shiftKey && document.activeElement === first) {
      ev.preventDefault();
      last.focus();
    } else if (!ev.shiftKey && document.activeElement === last) {
      ev.preventDefault();
      first.focus();
    }
  }

  // ── Tabs ─────────────────────────────────────────────────
  /** Swaps panels in place rather than re-rendering, so keyboard focus survives. */
  function showTab(tab) {
    if (TABS.indexOf(tab) < 0 || !root) return;
    activeTab = tab;
    writeTab(tab);
    TABS.forEach(function (key) {
      var btn = root.querySelector('[data-hb-tab="' + key + '"]');
      var panel = root.querySelector('[data-hb-panel="' + key + '"]');
      var on = key === tab;
      if (btn) {
        btn.setAttribute('aria-selected', String(on));
        btn.setAttribute('tabindex', on ? '0' : '-1');
      }
      if (panel) panel.hidden = !on;
    });
    var tools = root.querySelector('.hbt-tools');
    if (tools) tools.innerHTML = toolsHtml(tab, lastView);
    var agTab = root.querySelector('[data-hb-tab="ag"]');
    if (agTab) {
      var oldPill = agTab.querySelector('.hbt-n');
      if (oldPill) oldPill.parentNode.removeChild(oldPill);
      agTab.insertAdjacentHTML('beforeend', pillHtml(tab, lastView));
    }
    if (typeof handlers.onTabChange === 'function') handlers.onTabChange(tab);
  }

  function moveTab(step) {
    var idx = TABS.indexOf(activeTab);
    var next = TABS[(idx + step + TABS.length) % TABS.length];
    showTab(next);
    focusTab(next);
  }

  // ── Wiring ───────────────────────────────────────────────
  function onClick(ev) {
    var t = ev.target;
    if (!t || typeof t.closest !== 'function') return;

    var cancel = t.closest('[data-hb-cancel]');
    if (cancel) { ev.preventDefault(); closeConfirm(); return; }

    var confirmDel = t.closest('[data-hb-confirm-delete]');
    if (confirmDel) {
      ev.preventDefault();
      closeConfirm();
      if (typeof handlers.onConfirmDelete === 'function') handlers.onConfirmDelete();
      return;
    }

    if (t.closest('[data-hb-scrim]') && !t.closest('.cfm')) return; // backdrop is inert

    var more = t.closest('[data-hb-more]');
    if (more) { ev.preventDefault(); ev.stopPropagation(); openMenu(more); return; }

    var del = t.closest('[data-hb-delete]');
    if (del) {
      ev.preventDefault();
      var slotIndex = del.getAttribute('data-slot');
      closeMenu(false);
      if (typeof handlers.onRequestDelete === 'function') handlers.onRequestDelete(slotIndex);
      return;
    }

    var tab = t.closest('[data-hb-tab]');
    if (tab) { ev.preventDefault(); showTab(tab.getAttribute('data-hb-tab')); return; }

    var lbView = t.closest('[data-hb-lb-view]');
    if (lbView) {
      ev.preventDefault();
      if (typeof handlers.onLeaderboardView === 'function') {
        handlers.onLeaderboardView(lbView.getAttribute('data-hb-lb-view'));
      }
      return;
    }

    var byTeam = t.closest('[data-hb-by-team]');
    if (byTeam) {
      ev.preventDefault();
      if (typeof handlers.onLeadersByTeam === 'function') handlers.onLeadersByTeam();
      return;
    }

    var newF = t.closest('[data-hb-new-franchise]');
    if (newF) {
      ev.preventDefault();
      if (typeof handlers.onNewFranchise === 'function') {
        handlers.onNewFranchise(Number(newF.getAttribute('data-slot')));
      }
      return;
    }

    var logout = t.closest('[data-hb-logout]');
    if (logout) {
      ev.preventDefault();
      if (typeof handlers.onLogout === 'function') handlers.onLogout();
      return;
    }

    var settings = t.closest('[data-hb-settings]');
    if (settings) {
      ev.preventDefault();
      if (typeof handlers.onSettings === 'function') handlers.onSettings();
      return;
    }

    // Enter button first, then the card that repeats it.
    var enter = t.closest('[data-hb-enter]') || t.closest('[data-hb-door]');
    if (enter) {
      ev.preventDefault();
      closeMenu(false);
      if (typeof handlers.onEnter === 'function') {
        handlers.onEnter(enter.getAttribute('data-franchise-id'));
      }
      return;
    }

    if (openMenuSlot) closeMenu(false);
  }

  function onKeydown(ev) {
    var host = confirmHost();
    if (host && !host.hidden) {
      if (ev.key === 'Escape') { ev.preventDefault(); closeConfirm(); return; }
      if (ev.key === 'Tab') { trapFocus(ev); }
      return;
    }

    if (ev.key === 'Escape' && openMenuSlot) { ev.preventDefault(); closeMenu(true); return; }

    var t = ev.target;
    if (!t || typeof t.closest !== 'function') return;

    if (t.closest('[data-hb-tab]')) {
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') { ev.preventDefault(); moveTab(1); return; }
      if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') { ev.preventDefault(); moveTab(-1); return; }
      if (ev.key === 'Home') { ev.preventDefault(); showTab(TABS[0]); focusTab(TABS[0]); return; }
      if (ev.key === 'End') { ev.preventDefault(); showTab(TABS[TABS.length - 1]); focusTab(TABS[TABS.length - 1]); return; }
    }

    var door = t.closest('[data-hb-door]');
    if (door && (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar')) {
      ev.preventDefault();
      if (typeof handlers.onEnter === 'function') handlers.onEnter(door.getAttribute('data-franchise-id'));
    }
  }

  function focusTab(tab) {
    var btn = root && root.querySelector('[data-hb-tab="' + tab + '"]');
    if (btn) btn.focus();
  }

  function init(mountEl, opts) {
    root = mountEl;
    handlers = opts || {};
    activeTab = readTab();
    if (!root) return;
    // The dialog host is a sibling of the surface so a re-render never wipes an
    // open confirm, and it still inherits the .gob density class from the root.
    root.innerHTML = '<div id="hb-surface"></div><div id="hb-confirm-host" hidden></div>';
    surface = root.querySelector('#hb-surface');
    root.addEventListener('click', onClick);
    document.addEventListener('keydown', onKeydown);
    document.addEventListener('click', function (ev) {
      if (!openMenuSlot) return;
      if (root.contains(ev.target)) return;
      closeMenu(false);
    });
  }

  global.GOBHomeBase = {
    init: init,
    render: render,
    renderAround: renderAround,
    renderLeaderboard: renderLeaderboard,
    openConfirm: openConfirm,
    closeConfirm: closeConfirm,
    getTab: function () { return activeTab; },
    setTab: function (tab) { if (TABS.indexOf(tab) >= 0) { activeTab = tab; writeTab(tab); } },
    TAB_STORAGE_KEY: TAB_STORAGE_KEY,
  };
})(window);
