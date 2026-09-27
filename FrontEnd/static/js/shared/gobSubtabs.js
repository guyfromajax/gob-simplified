/**
 * Underline section tab row. One implementation for every section.
 * Adding a tab is a SECTIONS entry in gobShell.js; this file does not
 * know the lists.
 */
(function () {
  'use strict';

  var LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/></svg>';
  var CHEV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 9.5L12 15l5.5-5.5"/></svg>';
  var SEARCH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>';

  function esc(text) {
    return String(text || '').replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function tabsEl(host) {
    return host.querySelector('.tabs');
  }

  function directTabs(host) {
    var root = tabsEl(host);
    if (!root) return [];
    return Array.prototype.filter.call(root.children, function (el) {
      return el.classList && el.classList.contains('tb');
    });
  }

  function visibleTabs(host) {
    var list = directTabs(host).filter(function (tab) {
      return !tab.classList.contains('ovf');
    });
    var more = host.querySelector('.more-w.show .more');
    if (more) list.push(more);
    return list;
  }

  function placeInk(host) {
    var ink = host.querySelector('.ink');
    var tabs = host.querySelector('.tabs');
    var tab = host.querySelector('.tabs > .tb[aria-selected="true"]');
    if (!ink) return;
    if (!tab || !tabs || tab.classList.contains('ovf')) {
      ink.style.width = '0px';
      return;
    }
    var origin = tabs.getBoundingClientRect().left;
    var box = tab.getBoundingClientRect();
    ink.style.width = box.width + 'px';
    ink.style.transform = 'translateX(' + (box.left - origin) + 'px)';
    if (!ink.classList.contains('ready')) {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          if (ink.isConnected) ink.classList.add('ready');
        });
      });
    }
  }

  function placeMenu(host) {
    var menu = host.querySelector('.mmenu');
    var wrap = host.querySelector('.more-w');
    if (!menu || !wrap || !menu.classList.contains('open')) return;
    menu.style.left = 'auto';
    menu.style.right = '0';
    var box = menu.getBoundingClientRect();
    var limit = host.getBoundingClientRect();
    if (box.left < limit.left - 1) {
      menu.style.right = 'auto';
      menu.style.left = '0';
    }
  }

  function closeMenu(host, focusMore) {
    var menu = host.querySelector('.mmenu');
    var more = host.querySelector('.more');
    if (menu) menu.classList.remove('open');
    if (more) more.setAttribute('aria-expanded', 'false');
    if (focusMore && more) more.focus();
  }

  function openMenu(host) {
    var menu = host.querySelector('.mmenu');
    var more = host.querySelector('.more');
    if (!menu || !more || !host.querySelector('.more-w.show')) return;
    menu.classList.add('open');
    more.setAttribute('aria-expanded', 'true');
    placeMenu(host);
    var first = menu.querySelector('.mi');
    if (first) first.focus();
  }

  function menuItems(host) {
    var menu = host.querySelector('.mmenu');
    if (!menu) return '';
    var html = directTabs(host).filter(function (tab) {
      return tab.classList.contains('ovf');
    }).map(function (tab) {
      var label = tab.querySelector('.tb-l');
      var text = label ? label.textContent : '';
      var locked = tab.getAttribute('aria-disabled') === 'true';
      var week = tab.getAttribute('data-lock-week') || '';
      return '<button type="button" class="mi" role="menuitem" tabindex="-1" data-key="'
        + esc(tab.dataset.key || '') + '"' + (locked ? ' aria-disabled="true"' : '') + '>'
        + esc(text) + (locked ? LOCK + '<em>Unlocks Week ' + esc(week) + '</em>' : '')
        + '</button>';
    }).join('');
    if (menu.getAttribute('data-built') !== html) {
      var open = menu.classList.contains('open');
      menu.innerHTML = html;
      menu.setAttribute('data-built', html);
      if (open) menu.classList.add('open');
    }
    return html;
  }

  function overflowing(host) {
    return host.scrollWidth > host.clientWidth + 1;
  }

  function fit(host) {
    if (!host || host.__fitting) return;
    host.__fitting = true;
    try {
      var tabs = directTabs(host);
      var moreWrap = host.querySelector('.more-w');
      var input = host.querySelector('.gob-search');
      var sbtn = host.querySelector('.sbtn');
      tabs.forEach(function (tab) { tab.classList.remove('ovf'); });
      if (moreWrap) moreWrap.classList.remove('show');
      if (input && sbtn) {
        input.classList.remove('is-collapsed');
        sbtn.classList.remove('show');
        if (host.dataset.searchOpen !== '1' && overflowing(host)) {
          input.classList.add('is-collapsed');
          sbtn.classList.add('show');
        }
      }
      if (overflowing(host) && moreWrap) {
        moreWrap.classList.add('show');
        var i;
        for (i = tabs.length - 1; i >= 0 && overflowing(host); i--) {
          if (tabs[i].getAttribute('aria-selected') === 'true') continue;
          tabs[i].classList.add('ovf');
        }
      }
      menuItems(host);
      if (!moreWrap || !moreWrap.classList.contains('show')) closeMenu(host, false);
      placeInk(host);
      placeMenu(host);
      var current = host.querySelector('.tabs > .tb[tabindex="0"]');
      if (current && current.classList.contains('ovf')) restoreRoving(host);
    } finally {
      host.__fitting = false;
    }
  }

  function restoreRoving(host) {
    var selected = host.querySelector('.tabs > .tb[aria-selected="true"]');
    var tabs = visibleTabs(host);
    var keep = selected && tabs.indexOf(selected) >= 0 ? selected : (tabs[0] || null);
    directTabs(host).forEach(function (tab) { tab.tabIndex = tab === keep ? 0 : -1; });
    var more = host.querySelector('.more');
    if (more) more.tabIndex = more === keep ? 0 : -1;
  }

  function activateTab(tab) {
    if (!tab || tab.classList.contains('more')) return;
    if (tab.getAttribute('aria-disabled') === 'true') return;
    if (typeof tab._gobActivate === 'function') tab._gobActivate();
  }

  function tabFromMenuItem(host, item) {
    var key = item.getAttribute('data-key') || '';
    var found = null;
    directTabs(host).forEach(function (tab) {
      if (tab.dataset.key === key) found = tab;
    });
    return found;
  }

  function onKey(host, event) {
    var item = event.target.closest ? event.target.closest('.mi') : null;
    if (item && host.contains(item)) {
      var items = Array.prototype.slice.call(host.querySelectorAll('.mmenu .mi'));
      var index = items.indexOf(item);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        items[(index + step + items.length) % items.length].focus();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closeMenu(host, true);
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (item.getAttribute('aria-disabled') === 'true') return;
        var picked = tabFromMenuItem(host, item);
        closeMenu(host, false);
        activateTab(picked);
      }
      return;
    }
    if (event.target.classList && event.target.classList.contains('gob-search') && event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      event.target.value = '';
      event.target.dispatchEvent(new Event('input', { bubbles: true }));
      event.target.blur();
      return;
    }
    var current = event.target.closest ? event.target.closest('.tb') : null;
    if (!current || !host.contains(current)) return;
    if (current.classList.contains('more') && (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown')) {
      event.preventDefault();
      if (host.querySelector('.mmenu.open')) closeMenu(host, false);
      else openMenu(host);
      return;
    }
    if ((event.key === 'Enter' || event.key === ' ') && current.getAttribute('aria-disabled') === 'true') {
      event.preventDefault();
      return;
    }
    var vis = visibleTabs(host);
    var at = vis.indexOf(current);
    if (at < 0) return;
    var next = null;
    if (event.key === 'ArrowRight') next = vis[(at + 1) % vis.length];
    else if (event.key === 'ArrowLeft') next = vis[(at - 1 + vis.length) % vis.length];
    else if (event.key === 'Home') next = vis[0];
    else if (event.key === 'End') next = vis[vis.length - 1];
    if (!next) return;
    event.preventDefault();
    vis.forEach(function (tab) { tab.tabIndex = -1; });
    next.tabIndex = 0;
    next.focus();
    if (!next.classList.contains('more') && next.getAttribute('aria-disabled') !== 'true') {
      if (next.getAttribute('aria-selected') !== 'true') activateTab(next);
    }
  }

  function onClick(host, event) {
    var item = event.target.closest ? event.target.closest('.mi') : null;
    if (item && host.contains(item)) {
      event.preventDefault();
      if (item.getAttribute('aria-disabled') === 'true') return;
      var picked = tabFromMenuItem(host, item);
      closeMenu(host, false);
      activateTab(picked);
      return;
    }
    var tab = event.target.closest ? event.target.closest('.tb') : null;
    if (!tab || !host.contains(tab)) return;
    if (tab.classList.contains('more')) {
      event.preventDefault();
      if (host.querySelector('.mmenu.open')) closeMenu(host, false);
      else openMenu(host);
      return;
    }
    if (tab.getAttribute('aria-disabled') === 'true') {
      event.preventDefault();
      return;
    }
    if (tab.tagName === 'A') event.preventDefault();
    activateTab(tab);
  }

  function ensureSbtn(host) {
    var input = host.querySelector('.gob-search');
    var existing = host.querySelector('.sbtn');
    if (!input) {
      if (existing) existing.remove();
      return;
    }
    if (!existing) {
      existing = document.createElement('button');
      existing.type = 'button';
      existing.className = 'sbtn';
      existing.innerHTML = SEARCH;
      input.insertAdjacentElement('afterend', existing);
      existing.addEventListener('click', function () {
        host.dataset.searchOpen = '1';
        fit(host);
        var field = host.querySelector('.gob-search');
        if (field) field.focus();
      });
    }
    var label = input.getAttribute('aria-label') || input.getAttribute('placeholder') || 'Search';
    existing.setAttribute('aria-label', label);
  }

  function ensure(host) {
    if (host.__gobSubtabs) return;
    host.__gobSubtabs = true;
    host.addEventListener('click', function (event) { onClick(host, event); });
    host.addEventListener('keydown', function (event) { onKey(host, event); });
    host.addEventListener('focusout', function (event) {
      var next = event.relatedTarget;
      if (next && host.contains(next)) return;
      if (host.querySelector('.mmenu.open')) return;
      restoreRoving(host);
    });
    document.addEventListener('mousedown', function (event) {
      if (!host.contains(event.target)) closeMenu(host, false);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return;
      var target = event.target;
      if (!target || !host.isConnected) return;
      if (target.closest && target.closest('input, textarea, select, [contenteditable="true"]')) return;
      var input = host.querySelector('.gob-search');
      if (!input) return;
      event.preventDefault();
      host.dataset.searchOpen = '1';
      fit(host);
      var field = host.querySelector('.gob-search');
      if (field) field.focus();
    });
    if (window.ResizeObserver) {
      var observer = new ResizeObserver(function () { fit(host); });
      observer.observe(host);
    }
    if (window.MutationObserver) {
      var mutations = new MutationObserver(function () {
        if (host.__fitting) return;
        ensureSbtn(host);
        fit(host);
      });
      mutations.observe(host, { childList: true, subtree: true });
    }
    if (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === 'function') {
      document.fonts.ready.then(function () { if (host.isConnected) fit(host); });
    }
  }

  function render(host, model) {
    if (!host) return;
    var tabs = (model && model.tabs) || [];
    var selected = model && model.selected ? String(model.selected) : '';
    var label = model && model.label ? model.label : 'Section';
    host.dataset.searchOpen = '0';
    host.hidden = !tabs.length;
    if (!tabs.length) {
      host.innerHTML = '';
      return;
    }
    var html = '<div class="tabs" role="tablist" aria-label="' + esc(label) + ' sections">';
    tabs.forEach(function (item, index) {
      var key = item.link || item.id;
      var locked = !!item.lockedWeek;
      var on = !locked && selected && (selected === item.id || selected === item.link);
      var id = 'gob-tb-' + String(item.id || index);
      var labelId = id + '-l';
      if (locked) {
        html += '<button type="button" class="tb is-locked" role="tab" id="' + esc(id) + '" data-key="'
          + esc(key) + '" data-lock-week="' + esc(item.lockedWeek) + '" aria-labelledby="' + esc(labelId)
          + '" aria-selected="false" aria-disabled="true" tabindex="-1" aria-describedby="'
          + esc(id) + '-tip"><span class="tb-l" id="' + esc(labelId) + '">' + esc(item.label) + '</span>' + LOCK
          + '<span class="ltip" id="' + esc(id) + '-tip" role="tooltip"><b>Opens Week ' + esc(item.lockedWeek)
          + '</b><span>Tournament opens when the regular season ends.</span></span></button>';
      } else if (item.link) {
        html += '<a class="tb" role="tab" id="' + esc(id) + '" href="#" data-key="' + esc(key) + '" data-link="'
          + esc(item.link) + '" aria-labelledby="' + esc(labelId) + '" aria-selected="' + (on ? 'true' : 'false')
          + '" tabindex="' + (on ? '0' : '-1') + '"><span class="tb-l" id="' + esc(labelId) + '">'
          + esc(item.label) + '</span></a>';
      } else {
        html += '<button type="button" class="tb" role="tab" id="' + esc(id) + '" data-key="' + esc(key)
          + '" data-tab="' + esc(item.id) + '" aria-labelledby="' + esc(labelId) + '" aria-selected="'
          + (on ? 'true' : 'false') + '" tabindex="' + (on ? '0' : '-1') + '"><span class="tb-l" id="'
          + esc(labelId) + '">' + esc(item.label) + '</span></button>';
      }
    });
    html += '<span class="more-w"><button type="button" class="tb more" aria-haspopup="menu" aria-expanded="false" tabindex="-1">More'
      + CHEV + '</button><div class="mmenu" role="menu"></div></span><i class="ink" aria-hidden="true"></i></div>';
    host.innerHTML = html;
    directTabs(host).forEach(function (el, index) {
      el._gobActivate = function () {
        if (model && typeof model.onActivate === 'function') model.onActivate(tabs[index]);
      };
    });
    if (!host.querySelector('.tabs > .tb[aria-selected="true"]')) restoreRoving(host);
    var chosen = host.querySelector('.tabs > .tb[aria-selected="true"]');
    if (chosen && chosen.dataset.tab) {
      var panel = document.getElementById(chosen.dataset.tab);
      if (panel) {
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', chosen.id);
      }
    }
    ensure(host);
  }

  function select(host, key) {
    if (!host) return;
    key = key ? String(key) : '';
    directTabs(host).forEach(function (tab) {
      var on = tab.getAttribute('aria-disabled') !== 'true' && !!key
        && (tab.dataset.tab === key || tab.dataset.link === key);
      tab.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    restoreRoving(host);
    var chosen = host.querySelector('.tabs > .tb[aria-selected="true"]');
    if (chosen && chosen.dataset.tab) {
      var panel = document.getElementById(chosen.dataset.tab);
      if (panel) {
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', chosen.id);
      }
    }
    fit(host);
  }

  function syncTools(host) {
    if (!host) return;
    ensure(host);
    ensureSbtn(host);
    fit(host);
  }

  window.GOBSubtabs = {
    render: render,
    select: select,
    syncTools: syncTools,
    fit: fit
  };
})();
