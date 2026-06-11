(function () {
  'use strict';

  var params = new URLSearchParams(window.location.search);
  var franchiseId = params.get('franchise_id');
  var teamId = params.get('team_id');
  var storyId = params.get('story');

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fetchJSON(url) {
    var headers = window.API_CONFIG ? API_CONFIG.getAuthHeaders() : {};
    return fetch(url, { headers: headers }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          throw new Error(text || 'Request failed');
        });
      }
      return res.json();
    });
  }

  function baseQuery() {
    var q = new URLSearchParams();
    if (franchiseId) q.set('franchise_id', franchiseId);
    if (teamId) q.set('team_id', teamId);
    return q;
  }

  function buildNewsUrl(targetStoryId) {
    var q = baseQuery();
    if (targetStoryId) q.set('story', targetStoryId);
    var query = q.toString();
    return '/news.html' + (query ? '?' + query : '');
  }

  function buildBackToFccUrl() {
    if (typeof window.resolveFranchiseLockerRoomUrl === 'function') {
      return window.resolveFranchiseLockerRoomUrl({
        franchiseId: franchiseId,
        teamId: teamId
      });
    }
    var q = baseQuery();
    q.set('mode', 'franchise');
    return '/franchise-command-center.html?' + q.toString();
  }

  function renderEmpty(container, message) {
    container.innerHTML = '<div class="news-week-card"><div class="news-empty">' + escapeHtml(message) + '</div></div>';
  }

  function renderStoryView(container, story) {
    container.innerHTML = [
      '<div>',
      '<a class="brand-back-link news-back-to-list" href="' + buildNewsUrl(null) + '">Back to All News</a>',
      '<section class="news-story-card">',
      '<div class="news-story-meta">Week ' + escapeHtml(story.week) + '</div>',
      '<h2 class="news-story-headline">' + escapeHtml(story.headline) + '</h2>',
      '<div class="news-story-body">',
      (story.lines || []).map(function (line) {
        return '<p class="news-story-line">' + escapeHtml(line) + '</p>';
      }).join(''),
      '</div>',
      '</section>',
      '</div>'
    ].join('');
  }

  function renderListView(container, news) {
    if (!news.length) {
      renderEmpty(container, 'No News To Report');
      return;
    }

    // Group stories by release week, newest week first.
    var byWeek = {};
    news.forEach(function (story) {
      var week = Number(story.week || 0);
      (byWeek[week] = byWeek[week] || []).push(story);
    });
    var weeks = Object.keys(byWeek).map(Number).sort(function (a, b) { return b - a; });

    container.innerHTML = weeks.map(function (week) {
      return [
        '<section class="news-week-card">',
        '<div class="news-week-title">Week ' + week + '</div>',
        '<div class="news-week-body">',
        byWeek[week].map(function (story) {
          return '<a class="news-headline-link" href="' + buildNewsUrl(story.story_id) + '">' + escapeHtml(story.headline) + '</a>';
        }).join(''),
        '</div>',
        '</section>'
      ].join('');
    }).join('');
  }

  function init() {
    var container = document.getElementById('news-container');
    var backBtn = document.getElementById('back-btn');
    if (backBtn) backBtn.href = buildBackToFccUrl();

    if (!franchiseId) {
      renderEmpty(container, 'Missing franchise context.');
      return;
    }

    fetchJSON(API_CONFIG.buildUrl('/franchise/news') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (data) {
        var news = data.news || [];
        if (storyId) {
          var story = news.find(function (item) { return item.story_id === storyId; });
          if (story) {
            renderStoryView(container, story);
            return;
          }
        }
        renderListView(container, news);
      })
      .catch(function (err) {
        console.error(err);
        renderEmpty(container, 'Failed to load news.');
      });
  }

  init();
})();
