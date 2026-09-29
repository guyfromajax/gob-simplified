/**
 * News › News. Newest first: the top story is full width, then a 2- or 3-column
 * grid. The whole headline is the link. Game results append " (Box Score)" and
 * open the box score. Other rows open the story or the dispatch target.
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
    container.querySelectorAll('a.gob-news-card[data-story]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        var id = link.getAttribute('data-story');
        if (!id) return;
        event.preventDefault();
        openStory(id);
      });
    });
  }

  function isGameResult(item) {
    return item && (item.type === 'game_result' || !!(item.box_score_href || (item.target && String(item.target).indexOf('box-score') !== -1)));
  }

  function cardHref(item) {
    if (isGameResult(item)) return item.box_score_href || item.target || '';
    if (item.story_id) return storyUrl(item.story_id);
    return item.target || '';
  }

  function cardHeadline(item) {
    var text = String(item.headline || '').replace(/\s*\(Box Score\)\s*$/i, '');
    if (isGameResult(item)) return text + ' (Box Score)';
    return text;
  }

  function cardHtml(item, hero) {
    var href = cardHref(item);
    var cls = 'gob-news-card' + (hero ? ' is-hero' : '') + (item.yours ? ' is-yours' : '');
    var inner = '<span class="gob-news-type">' + tables.esc(typeLabel(item.type)) + '</span>'
      + '<p>' + tables.esc(cardHeadline(item)) + '</p>'
      + '<span class="gob-news-when">Week ' + tables.esc(item.week) + '</span>';
    var story = item.story_id && !isGameResult(item) ? ' data-story="' + tables.esc(item.story_id) + '"' : '';
    if (!href) return '<div class="' + cls + '"' + story + '>' + inner + '</div>';
    return '<a class="' + cls + '"' + story + ' href="' + tables.esc(href) + '">' + inner + '</a>';
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
    var items = [];
    dispatches.forEach(function (item) { if (item) items.push(item); });
    news.forEach(function (item) { if (item) items.push(item); });
    items.sort(function (a, b) {
      var week = Number(b.week || 0) - Number(a.week || 0);
      if (week) return week;
      if (a.yours && !b.yours) return -1;
      if (!a.yours && b.yours) return 1;
      return 0;
    });
    if (!items.length) {
      container.innerHTML = '<p class="gob-news-empty">No News To Report</p>';
      return;
    }
    var html = '<div class="gob-news">';
    html += cardHtml(items[0], true);
    if (items.length > 1) {
      html += '<div class="gob-news-grid">';
      items.slice(1).forEach(function (item) { html += cardHtml(item, false); });
      html += '</div>';
    }
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
