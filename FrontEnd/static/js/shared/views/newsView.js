/**
 * News › News. Stored headlines, newest week first.
 * A headline opens the stored story body in this panel (a push).
 * Dispatches are yours=true rows from GET /franchise/news. Headlines stay plain text.
 */

import { renderStoryBody } from '/js/shared/newsStory.js';

function typeLabel(type) {
  var known = {
    walk_ons_announced: 'Walk-ons',
    upset_report: 'Upset report',
    ps_all_stars: 'Practice Squad',
    ps_rosters_announced: 'Practice Squad',
    ps_game_results: 'Practice Squad',
    recruiting_report: 'Recruiting',
    recruiting_results: 'Recruiting',
    recruiting_leans: 'Recruiting',
    recruiting_movement: 'Recruiting',
    training_report: 'Training report',
    training_squad_report: 'Practice Squad',
    game_result: 'Game result'
  };
  if (known[type]) return known[type];
  return String(type || '').split('_').filter(Boolean).map(function (word) {
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ');
}

function storyParam() {
  try { return new URLSearchParams(window.location.search).get('story') || ''; }
  catch (err) { return ''; }
}

function feedUrl() {
  var params = new URLSearchParams(window.location.search);
  params.delete('story');
  params.set('tab', 'news-view');
  var text = params.toString();
  return window.location.pathname + (text ? '?' + text : '');
}

function presentLabel(label) {
  return String(label || '').replace(/\b\w/g, function (letter) {
    return letter.toUpperCase();
  });
}

function storyUrl(id) {
  var params = new URLSearchParams(window.location.search);
  params.set('tab', 'news-view');
  params.set('story', id);
  var text = params.toString();
  return window.location.pathname + (text ? '?' + text : '');
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var body = null;
  var signature = '';
  var loaded = false;
  var alive = true;

  function clearStoryContext() {
    var current = storyParam();
    if (current) return;
    if (window.FranchiseContext && typeof window.FranchiseContext.set === 'function') {
      window.FranchiseContext.set('story', '');
    }
  }

  function openStory(id) {
    if (window.GOBViews && typeof window.GOBViews.open === 'function') {
      window.GOBViews.open(storyUrl(id), 'push');
    }
    if (window.FranchiseContext && typeof window.FranchiseContext.set === 'function') {
      window.FranchiseContext.set('story', id);
    }
  }

  function bindFeed() {
    container.querySelectorAll('a.gob-news-row').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        var id = link.getAttribute('data-story');
        if (!id) return;
        event.preventDefault();
        openStory(id);
      });
    });
  }

  function render() {
    if (!alive) return;
    clearStoryContext();
    var news = (body && body.news) || [];
    var dispatches = (body && body.dispatches) || [];
    var openId = storyParam();
    if (openId) {
      var story = null;
      news.forEach(function (item) {
        if (!story && item && item.story_id === openId) story = item;
      });
      if (story) {
        container.innerHTML = '<div class="gob-news-story"><a class="gob-dt-up" id="back-button" data-gob-up="'
          + tables.esc(feedUrl()) + '" href="'
          + tables.esc(feedUrl()) + '">← News</a><h2 class="gob-news-headline">'
          + tables.esc(story.headline || '') + '</h2><p class="gob-news-meta">Week '
          + tables.esc(story.week) + '</p><div class="gob-news-body">'
          + renderStoryBody(story) + '</div></div>';
        if (window.GOBTables && typeof window.GOBTables.bindWide === 'function') {
          window.GOBTables.bindWide(container);
        }
        return;
      }
    }
    if (!news.length && !dispatches.length) {
      container.innerHTML = '<p class="gob-news-empty">No News To Report</p>';
      return;
    }
    var byWeek = Object.create(null);
    var order = [];
    function bucket(week) {
      var key = String(Number(week || 0));
      if (!byWeek[key]) {
        byWeek[key] = { week: Number(week || 0), mine: [], stories: [] };
        order.push(key);
      }
      return byWeek[key];
    }
    dispatches.forEach(function (item) {
      if (!item || !Number.isFinite(Number(item.week))) return;
      bucket(item.week).mine.push(item);
    });
    news.forEach(function (item) { bucket(item.week).stories.push(item); });
    order.sort(function (a, b) { return Number(b) - Number(a); });
    var html = '<div class="gob-news">';
    order.forEach(function (key) {
      var group = byWeek[key];
      html += '<section class="gob-news-week"><h3>Week ' + tables.esc(group.week) + '</h3><div class="gob-tcard gob-news-card">';
      group.mine.forEach(function (item) {
        html += '<div class="gob-news-row' + (item.yours ? ' is-yours' : '') + '">'
          + '<span class="gob-news-type">' + tables.esc(typeLabel(item.type)) + '</span>'
          + '<p>' + tables.esc(item.headline || '') + '</p>';
        if (item.target) {
          html += '<a class="lnk" href="' + tables.esc(item.target) + '">'
            + tables.esc(presentLabel(item.link_label || '')) + '</a>';
        }
        html += '</div>';
      });
      group.stories.forEach(function (item) {
        html += '<a class="gob-news-row" data-story="' + tables.esc(item.story_id || '') + '" href="'
          + tables.esc(storyUrl(item.story_id || '')) + '">'
          + '<span class="gob-news-type">' + tables.esc(typeLabel(item.type)) + '</span>'
          + '<p>' + tables.esc(item.headline || '') + '</p></a>';
      });
      html += '</div></section>';
    });
    html += '</div>';
    container.innerHTML = html;
    bindFeed();
  }

  function apply(next) {
    var stamp = JSON.stringify(next || {});
    if (loaded && stamp === signature && storyParam() === apply.story) {
      return;
    }
    signature = stamp;
    apply.story = storyParam();
    body = next || { news: [], dispatches: [] };
    loaded = true;
    render();
  }

  function fail() {
    if (!alive) return;
    tables.paintError(container, 'Failed to load news.', load);
  }

  function load() {
    var store = ctx && ctx.store;
    var franchiseId = (ctx && ctx.franchiseId) || '';
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      fail();
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(tables.apiBase('/franchise/news') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (payload) { apply(payload); })
      .catch(fail);
  }

  function revalidate() {
    var store = ctx && ctx.store;
    var franchiseId = (ctx && ctx.franchiseId) || '';
    if (!store || !franchiseId) return;
    if (loaded && storyParam() !== apply.story) render();
    store.revalidate(tables.apiBase('/franchise/news') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (payload) {
        if (payload) apply(payload);
        else if (storyParam() !== apply.story) render();
      })
      .catch(function () {});
  }

  window.addEventListener('gob-tab-shown', onTab);
  load();

  function onTab() {
    if (container.classList.contains('active') && loaded) revalidate();
  }

  return {
    revalidate: revalidate,
    unmount: function () {
      alive = false;
      window.removeEventListener('gob-tab-shown', onTab);
    }
  };
}
