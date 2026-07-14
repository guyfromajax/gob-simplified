(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const franchiseId = params.get('franchise_id');
  const teamId = params.get('team_id');
  const backBtn = document.getElementById('back-btn');
  const CATEGORY_ORDER = ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'];
  const CATEGORY_LABELS = {
    PTS: 'Points',
    '3PTM': '3 PT Made',
    AST: 'Assists',
    BLK: 'Blocks',
    'FG%': 'FG%',
    REB: 'Rebounds',
    STL: 'Steals',
    'DEF%': 'DEF%',
  };

  let currentScope = 'conference';
  let leadersData = null;
  let resourceCache = null;

  function fetchJSON(url) {
    return fetch(url, { headers: API_CONFIG.getAuthHeaders() })
      .then((res) => {
        if (!res.ok) throw new Error('Request failed');
        return res.json();
      })
      .catch((error) => {
        console.error('Failed loading', url, error);
        return null;
      });
  }

  function formatLeaderValue(category, value) {
    if (value == null || value === '') return '--';
    const numeric = Number(value);
    if (category === 'DEF%') {
      return `${Number.isFinite(numeric) ? Math.round(numeric) : 0}%`;
    }
    if (category === 'FG%') {
      return `${Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0'}%`;
    }
    return Number.isFinite(numeric) ? numeric.toFixed(1).replace(/\.0$/, '') : String(value);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function render() {
    const grid = document.getElementById('leaders-grid');
    if (!grid) return;
    if (!leadersData) {
      grid.innerHTML = '<div class="leader-card"><div class="leader-card-empty">Failed to load leaders.</div></div>';
      return;
    }

    grid.innerHTML = '';
    CATEGORY_ORDER.forEach((category) => {
      const leaders = category === 'DEF%'
        ? []
        : (Array.isArray(leadersData[category]) ? leadersData[category].slice(0, 10) : []);
      const card = document.createElement('section');
      card.className = 'leader-card';
      const header = document.createElement('div');
      header.className = 'leader-card-header';
      header.textContent = CATEGORY_LABELS[category] || category;
      card.appendChild(header);
      const list = document.createElement('div');
      list.className = 'leader-card-list';
      if (!leaders.length) {
        list.innerHTML = '<div class="leader-card-empty">No leaders available.</div>';
      } else {
        leaders.forEach((leader, index) => {
          const row = document.createElement('div');
          row.className = 'leader-row';
          row.innerHTML = `
            <div class="leader-rank">${index + 1}.</div>
            <div class="leader-meta">
              <div class="leader-name">${escapeHtml(leader.name || '--')}</div>
              <div class="leader-team">${escapeHtml(leader.team || '--')}</div>
            </div>
            <div class="leader-value">${escapeHtml(formatLeaderValue(category, leader.value))}</div>
          `;
          list.appendChild(row);
        });
      }
      card.appendChild(list);
      grid.appendChild(card);
    });
  }

  async function loadScope(scope) {
    const cached = resourceCache && resourceCache.get(scope);
    if (cached) return cached;
    const payload = await fetchJSON(
      API_CONFIG.buildUrl('/franchise/leaders')
      + '?franchise_id=' + encodeURIComponent(franchiseId)
      + '&scope=season'
      + '&view_scope=' + encodeURIComponent(scope)
      + '&limit=10'
    );
    return resourceCache ? resourceCache.set(scope, payload) : payload;
  }

  function bindScopeButtons() {
    document.querySelectorAll('.stats-scope-btn').forEach((btn) => {
      btn.addEventListener('click', async function () {
        const scope = btn.getAttribute('data-scope') || 'conference';
        if (scope === currentScope) return;
        currentScope = scope;
        document.querySelectorAll('.stats-scope-btn').forEach((other) => {
          other.classList.toggle('active', other.getAttribute('data-scope') === currentScope);
        });
        const grid = document.getElementById('leaders-grid');
        if (grid) {
          grid.innerHTML = '<div class="leader-card"><div class="leader-card-empty">Loading leaders...</div></div>';
        }
        leadersData = await loadScope(currentScope);
        render();
      });
    });
  }

  async function init() {
    if (!franchiseId) {
      const grid = document.getElementById('leaders-grid');
      if (grid) {
        grid.innerHTML = '<div class="leader-card"><div class="leader-card-empty">Missing franchise_id in URL.</div></div>';
      }
      return;
    }

    if (backBtn && franchiseId && teamId) {
      backBtn.href = resolveFranchiseLockerRoomUrl({ params, franchiseId, teamId });
    }

    const topData = await fetchJSON(
      API_CONFIG.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId)
    );
    if (topData && window.ResourceCache && window.ResourceCache.createResourceCache) {
      resourceCache = window.ResourceCache.createResourceCache('leaders-v2', franchiseId, topData.current_season, topData.week);
    }

    leadersData = await loadScope(currentScope);
    render();
    bindScopeButtons();
  }

  init();
})();
