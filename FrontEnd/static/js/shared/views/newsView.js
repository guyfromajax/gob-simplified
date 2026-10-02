/**
 * News › News. Newest first, one section per week. The top story is full width, then
 * each week is a 2- or 3-column grid under its "Week N" heading. The whole headline is
 * the link. Game results append " (Box Score)" and open the box score. Other rows open
 * the story or the dispatch target.
 */

import { renderStoryBody, storyIsWide } from '/js/shared/newsStory.js';

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

// Keys left by an earlier drill-in (a team opened from the Office, say). The feed and a
// story are addressed by `tab` and `story` alone, so neither URL carries them.
function drillKeys() {
  var tables = window.GOBTables;
  return tables && typeof tables.drillKeys === 'function'
    ? tables.drillKeys()
    : ['story', 'player_id', 'view_team_id', 'return_tab', 'origin', 'return_url', 'up', 'pager'];
}

function cleanParams() {
  var params = new URLSearchParams(window.location.search);
  drillKeys().forEach(function (key) { params.delete(key); });
  params.delete('story');
  params.set('tab', 'news-view');
  return params;
}

function feedUrl() {
  var text = cleanParams().toString();
  return window.location.pathname + (text ? '?' + text : '');
}

function storyUrl(id) {
  var params = cleanParams();
  params.set('story', id);
  var text = params.toString();
  return window.location.pathname + (text ? '?' + text : '');
}

// Stamped on a story's history entry when it was opened from the feed: the entry behind
// it is then the feed, at the scroll the reader left it.
var FROM_FEED = 'gobNewsFromFeed';

function markFromFeed() {
  try {
    var state = {};
    var current = window.history.state || {};
    Object.keys(current).forEach(function (key) { state[key] = current[key]; });
    state[FROM_FEED] = true;
    window.history.replaceState(state, '');
  } catch (err) { /* "← News" then opens the feed in place */ }
}

function cameFromFeed() {
  try { return !!(window.history.state && window.history.state[FROM_FEED]); }
  catch (err) { return false; }
}

// True when the headline already names the story's week ("Week 9 Recruiting Report",
// "Week 3 Upset Report", "Projected All-Americans: week 7"), or names it in words
// ("… end of the regular season" is week 26): the "Week N" line under it would only
// repeat it.
function headlineNamesWeek(story) {
  var week = Number(story && story.week);
  if (!isFinite(week)) return false;
  var headline = String((story && story.headline) || '');
  if (/end of the regular season/i.test(headline)) return true;
  return new RegExp('\\bweek\\s+' + week + '\\b', 'i').test(headline);
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
      markFromFeed();
    }
    if (window.FranchiseContext && typeof window.FranchiseContext.set === 'function') {
      window.FranchiseContext.set('story', id);
    }
  }

  // "← News" always lands on the feed. Opened from the feed, the feed is the entry
  // behind this one: step back to it and its scroll comes back with it. Any other way
  // in (a direct URL, a link from another page or another story), the feed takes this
  // entry's place, so the browser's Back still returns to where the reader came from.
  function bindBack() {
    var link = container.querySelector('.gob-news-story a.gob-dt-up');
    if (!link) return;
    link.addEventListener('click', function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
      event.preventDefault();
      var feed = feedUrl();
      if (cameFromFeed() && window.GOBNav && typeof window.GOBNav.back === 'function') {
        window.GOBNav.back(feed);
        return;
      }
      if (window.GOBViews && typeof window.GOBViews.open === 'function') {
        window.GOBViews.open(feed, 'replace');
      } else {
        window.location.replace(feed);
      }
    });
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
    // The week is the section heading, so the card does not repeat it.
    var inner = '<span class="gob-news-type">' + tables.esc(typeLabel(item.type)) + '</span>'
      + '<p>' + tables.esc(cardHeadline(item)) + '</p>';
    var story = item.story_id && !isGameResult(item) ? ' data-story="' + tables.esc(item.story_id) + '"' : '';
    if (!href) return '<div class="' + cls + '"' + story + '>' + inner + '</div>';
    // A game result opens the box score as a read: GOBNav adds return_url on the click.
    var back = isGameResult(item) ? ' data-return' : '';
    return '<a class="' + cls + '"' + story + back + ' href="' + tables.esc(href) + '">' + inner + '</a>';
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
        // No "Week N" line under a headline that already names the week.
        var meta = headlineNamesWeek(story)
          ? ''
          : '<p class="gob-news-meta">Week ' + tables.esc(story.week) + '</p>';
        container.innerHTML = '<div class="gob-news-story' + (storyIsWide(story) ? ' is-wide' : '')
          + '"><a class="gob-dt-up" id="back-button" href="'
          + tables.esc(feedUrl()) + '">← News</a><h2 class="gob-news-headline">'
          + tables.esc(story.headline || '') + '</h2>' + meta + '<div class="gob-news-body">'
          + renderStoryBody(story) + '</div></div>';
        if (window.GOBTables && typeof window.GOBTables.bindWide === 'function') {
          window.GOBTables.bindWide(container);
        }
        bindBack();
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
    // One section per week, newest first. The feed's first story leads its week.
    var weeks = [];
    items.forEach(function (item) {
      var last = weeks[weeks.length - 1];
      if (!last || String(last.week) !== String(item.week)) {
        last = { week: item.week, items: [] };
        weeks.push(last);
      }
      last.items.push(item);
    });
    var html = '<div class="gob-news">';
    weeks.forEach(function (group, index) {
      var rest = index === 0 ? group.items.slice(1) : group.items;
      html += '<section class="gob-news-week" data-week="' + tables.esc(group.week) + '">'
        + '<h2 class="gob-news-wk">Week ' + tables.esc(group.week)
        + '<em>' + group.items.length + (group.items.length === 1 ? ' story' : ' stories') + '</em></h2>';
      if (index === 0) html += cardHtml(group.items[0], true);
      if (rest.length) {
        html += '<div class="gob-news-grid">';
        rest.forEach(function (item) { html += cardHtml(item, false); });
        html += '</div>';
      }
      html += '</section>';
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
