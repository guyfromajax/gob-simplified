(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var context = Recruiting.getQueryContext();
  var sortState = { key: 'rt', direction: 'desc' };
  var recruits = [];

  function render() {
    Recruiting.renderRecruitTableRows(
      document.getElementById('recruiting-body'),
      Recruiting.sortRecruits(recruits, sortState)
    );
  }

  function setOrdersButton(data) {
    var btn = document.getElementById('orders-btn');
    if (!btn) return;
    var week = Number(data.week || 1);
    var resultsWeek = Number(data.current_results_week || 0);
    if (week < 20 || week > 26) {
      btn.style.display = 'none';
      return;
    }
    btn.style.display = 'inline-flex';
    if (resultsWeek === week) {
      btn.textContent = 'Week ' + week + ' Recruiting Visits';
      btn.addEventListener('click', function () {
        window.location.href = Recruiting.buildRecruitingUrl('recruiting-results.html', context, { from: 'recruiting', week: String(week) });
      });
    } else {
      btn.textContent = 'Recruiting Orders';
      btn.addEventListener('click', function () {
        window.location.href = Recruiting.buildRecruitingUrl('recruiting-orders.html', context, { from: 'recruiting' });
      });
    }
  }

  function init() {
    if (!context.franchiseId || !context.teamId) {
      document.getElementById('recruiting-body').innerHTML = '<tr><td colspan="20">Missing franchise context.</td></tr>';
      return;
    }

    document.getElementById('back-btn').href = Recruiting.buildFccUrl(context);

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        recruits = Recruiting.normalizeRecruits(data.recruits || [], data.team_name_map || {});
        Recruiting.bindSortableHeaders(
          document.getElementById('recruiting-table'),
          sortState,
          render
        );
        render();
        setOrdersButton(data);
        if (typeof window.initAttributeTooltips === 'function') {
          window.initAttributeTooltips(document.getElementById('recruiting-table'), ['th']);
        }
      })
      .catch(function (err) {
        console.error(err);
        document.getElementById('recruiting-body').innerHTML = '<tr><td colspan="20">Failed to load recruits.</td></tr>';
      });
  }

  init();
})();
