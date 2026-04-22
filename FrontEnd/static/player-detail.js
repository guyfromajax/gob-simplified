(function () {
  const ATTRIBUTE_LAYOUT = [
    ['SC', 'ID', 'PS', 'RB', 'AG', 'IQ'],
    ['SH', 'OD', 'BH', 'ST', 'ND', 'FT']
  ];

  const POSITION_CONFIG = {
    PG: { color: '#4065AF', background: 'rgba(64,101,175,0.20)', fullName: 'POINT GUARD' },
    SG: { color: '#7B5EA7', background: 'rgba(123,94,167,0.20)', fullName: 'SHOOTING GUARD' },
    SF: { color: '#3A8C4A', background: 'rgba(58,140,74,0.20)', fullName: 'SMALL FORWARD' },
    PF: { color: '#C0392B', background: 'rgba(192,57,43,0.20)', fullName: 'POWER FORWARD' },
    C: { color: '#D4A017', background: 'rgba(212,160,23,0.20)', fullName: 'CENTER' }
  };

  function getHighestPosition(player) {
    // TODO: confirm position field name against actual player model
    const rawPosition = player?.position ?? player?.pos;
    if (Array.isArray(rawPosition)) {
      return String(rawPosition[0] || '--').toUpperCase();
    }
    if (typeof rawPosition === 'string' && rawPosition.trim()) {
      return rawPosition.trim().toUpperCase();
    }
    return '--';
  }

  function getPositionConfig(abbrev) {
    return POSITION_CONFIG[abbrev] || { color: 'rgba(255,255,255,0.72)', background: 'rgba(255,255,255,0.08)', fullName: 'PLAYER' };
  }

  function getAttrColor(scaledValue) {
    if (scaledValue <= 4) return '#ff6d6d';
    if (scaledValue <= 6) return '#FFD700';
    if (scaledValue <= 8) return '#34EC27';
    if (scaledValue <= 10) return '#4A90D9';
    return '#27408E';
  }

  function getEmotionEmoji(player) {
    const raw = Number(player?.em ?? player?.EM ?? player?.attributes?.EM ?? player?.attributes?.anchor_EM ?? 50);
    if (raw >= 80) return '😎';
    if (raw >= 60) return '😊';
    if (raw >= 40) return '😐';
    if (raw >= 20) return '😕';
    return '😡';
  }

  function renderAttributeRow(code, attributes) {
    const rawValue = attributes[`anchor_${code}`] ?? attributes[code] ?? 0;
    const scaledValue = Math.max(1, Math.floor(rawValue / 10));
    const fillPercentage = Math.min(100, scaledValue * 10);
    const row = document.createElement('div');
    row.className = 'pd-attribute-row';
    row.innerHTML = `
      <span class="pd-attribute-label attribute-label" data-attr="${code}">${code}</span>
      <div class="pd-attribute-track">
        <div class="pd-attribute-fill" data-width="${fillPercentage}" style="background:${getAttrColor(scaledValue)};"></div>
      </div>
      <span class="pd-attribute-value">${scaledValue}</span>
    `;
    return row;
  }

  function animateAttributeBars() {
    const bars = document.querySelectorAll('.pd-attribute-fill');
    bars.forEach((bar, index) => {
      setTimeout(() => {
        const targetWidth = bar.getAttribute('data-width');
        bar.style.width = `${targetWidth}%`;
      }, index * 40);
    });
  }

  function formatHeight(inches) {
    const feet = Math.floor(inches / 12);
    const remainingInches = inches % 12;
    return `${feet}'${remainingInches}"`;
  }

  function formatYear(year) {
    if (!year) return 'N/A';
    const yearStr = String(year).toLowerCase();
    const yearMap = {
      'senior': 'Senior',
      'junior': 'Junior',
      'sophomore': 'Sophomore',
      'freshman': 'Freshman',
      'sr': 'Senior',
      'jr': 'Junior',
      'so': 'Sophomore',
      'fr': 'Freshman'
    };
    return yearMap[yearStr] || year;
  }

  function normalizePhotoUrl(photoUrl, staticPrefix = '') {
    if (!photoUrl || typeof photoUrl !== 'string') return '';
    const trimmed = photoUrl.trim();
    if (!trimmed) return '';

    if (trimmed.startsWith('/static/images/')) {
      return `${staticPrefix}${trimmed.replace(/^\/static/, '')}`;
    }
    if (trimmed.startsWith('/images/')) {
      return `${staticPrefix}${trimmed}`;
    }
    return trimmed;
  }

  function getTeamId(teamName) {
    const teamMap = {
      'Bentley-Truman': 'BENTLEY_TRUMAN',
      'Four Corners': 'FOUR_CORNERS',
      'Lancaster': 'LANCASTER',
      'Little York': 'LITTLE_YORK',
      'Morristown': 'MORRISTOWN',
      'Ocean City': 'OCEAN_CITY',
      'South Lancaster': 'SOUTH_LANCASTER',
      'Xavien': 'XAVIEN'
    };
    return teamMap[teamName] || teamName.toUpperCase().replace(/\s+/g, '_');
  }

  function normalizeTeamName(teamName) {
    if (!teamName) return 'Free Agent';
    if (teamName.includes('_')) {
      const byId = {
        BENTLEY_TRUMAN: 'Bentley-Truman',
        FOUR_CORNERS: 'Four Corners',
        LANCASTER: 'Lancaster',
        LITTLE_YORK: 'Little York',
        MORRISTOWN: 'Morristown',
        OCEAN_CITY: 'Ocean City',
        SOUTH_LANCASTER: 'South Lancaster',
        XAVIEN: 'Xavien',
      };
      return byId[teamName] || teamName.replace(/_/g, ' ');
    }
    return teamName;
  }

  function getTeamBackground(teamName, staticPrefix = '') {
    if (typeof getTeamAssetPath === 'function') return staticPrefix + getTeamAssetPath(teamName, 'background');
    return staticPrefix + '/images/teams/general/general_background.png';
  }

  function getTeamLogo(teamName, staticPrefix = '') {
    if (typeof getTeamAssetPath === 'function') return staticPrefix + getTeamAssetPath(teamName, 'logo_square');
    return staticPrefix + '/images/teams/general/general_logo_square.png';
  }

  function goBack() {
    const params = new URLSearchParams(window.location.search);
    const returnUrl = params.get('return_url');
    if (returnUrl) {
      window.location.href = returnUrl;
      return;
    }

    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = '/static/homepage.html';
    }
  }

  function showError(message) {
    const content = document.getElementById('pd-content');
    content.innerHTML = `
      <div class="pd-error">
        <div class="pd-error-card">
          <div class="pd-error-title">Error</div>
          <div class="pd-error-copy">${message}</div>
          <button class="pd-back-btn" id="pd-error-back">Back</button>
        </div>
      </div>
    `;
    const btn = document.getElementById('pd-error-back');
    if (btn) btn.addEventListener('click', goBack);
  }

  function renderAttributes(attributes) {
    const grid = document.getElementById('pd-attributes-grid');
    if (!grid) return;
    grid.innerHTML = '';
    ATTRIBUTE_LAYOUT.forEach((codes) => {
      const col = document.createElement('div');
      col.className = 'pd-attributes-col';
      codes.forEach((code) => {
        col.appendChild(renderAttributeRow(code, attributes));
      });
      grid.appendChild(col);
    });
  }

  function renderCareerStats(player, team, teamColor) {
    const body = document.getElementById('pd-career-stats-body');
    if (!body) return;
    body.innerHTML = '';
    const seasonStats = Array.isArray(player?.season_stats) ? player.season_stats : [];
    const rows = seasonStats.length ? seasonStats : [{
      season: 'Current',
      team,
      gp: '--',
      pts: '--',
      reb: '--',
      ast: '--',
      stl: '--',
      blk: '--',
      fg_pct: '--',
      three_pct: '--'
    }];

    rows.forEach((season, index) => {
      const tr = document.createElement('tr');
      if (index === 0) tr.className = 'pd-current-season';
      const teamStyle = teamColor ? ` style="color:${teamColor}"` : '';
      tr.innerHTML = `
        <td class="pd-season-cell">${season.season ?? (index === 0 ? 'Current' : '--')}</td>
        <td class="pd-team-cell"${teamStyle}>${season.team ?? team ?? '--'}</td>
        <td class="pd-career-num">${season.gp ?? '--'}</td>
        <td class="pd-career-num">${season.pts ?? '--'}</td>
        <td class="pd-career-num">${season.reb ?? '--'}</td>
        <td class="pd-career-num">${season.ast ?? '--'}</td>
        <td class="pd-career-num">${season.stl ?? '--'}</td>
        <td class="pd-career-num">${season.blk ?? '--'}</td>
        <td class="pd-career-num">${season.fg_pct ?? '--'}</td>
        <td class="pd-career-num">${season.three_pct ?? '--'}</td>
      `;
      body.appendChild(tr);
    });
  }

  function buildPortrait(photo, fullName, genericPhoto, fallbackPhoto) {
    if (!photo) {
      return '<div class="pd-portrait-placeholder" aria-hidden="true"></div>';
    }
    const initialFallbackState = photo === fallbackPhoto ? 'player' : 'primary';
    return `<img src="${photo}" alt="${fullName}" class="pd-portrait" onerror="if(this.dataset.fallbackState==='generic'){this.remove();this.parentElement.innerHTML='<div class=&quot;pd-portrait-placeholder&quot; aria-hidden=&quot;true&quot;></div>';}else if(this.dataset.fallbackState==='player'){this.dataset.fallbackState='generic';this.src='${genericPhoto}';}else{this.dataset.fallbackState='player';this.src='${fallbackPhoto}';}" data-fallback-state="${initialFallbackState}">`;
  }

  function renderPlayerPage(player) {
    const content = document.getElementById('pd-content');
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const staticPrefix = isLocalhost ? '/static' : '';

    const firstName = player.first_name || '';
    const lastName = player.last_name || '';
    const fullName = `${firstName} ${lastName}`.trim() || 'Unknown Player';
    const rawTeam = player.team || 'Free Agent';
    const team = normalizeTeamName(rawTeam);
    const heightValue = player.height || player.HT || 75;
    const height = formatHeight(heightValue);
    const weightValue = player.weight || player.WT || '--';
    const jersey = (typeof player.jersey === 'number') ? player.jersey : (player.jersey !== undefined && player.jersey !== null && player.jersey !== '' ? player.jersey : '');
    const fallbackPhoto = `${staticPrefix}/images/players/${player._id}.png`;
    const genericPhoto = `${staticPrefix}/images/players/generic_headshot.png`;
    const photo = normalizePhotoUrl(player.photo, staticPrefix) || fallbackPhoto;
    const attributes = player.attributes || {};
    const year = formatYear(player.year);
    const positionAbbrev = getHighestPosition(player);
    const positionConfig = getPositionConfig(positionAbbrev);
    const rtValue = player.rt ?? player.RT ?? '--';
    const momentumValue = player.mo ?? player.momentum ?? '--';
    const emotionEmoji = getEmotionEmoji(player);
    const teamBackground = getTeamBackground(team, staticPrefix);
    const teamPrimaryColor = player.primary_color || POSITION_CONFIG[positionAbbrev]?.color || '';

    content.innerHTML = `
      <div class="resource-page-container fcc-brand-page-shell pd-shell">
        <aside class="pd-left-card">
          <button class="pd-back-btn" id="pd-back-btn">Back</button>
          <div class="pd-portrait-wrap" style="background-image:url('${teamBackground}');background-size:cover;background-position:center;">
            ${buildPortrait(photo, fullName, genericPhoto, fallbackPhoto)}
          </div>
          <div class="pd-player-name">${fullName}</div>
          <div class="pd-pos-line">${positionConfig.fullName} ${jersey !== '' ? `· #${jersey}` : ''}</div>
          <div class="pd-overall">
            <div class="pd-overall-label">OVERALL</div>
            <div class="pd-overall-value">${rtValue}</div>
          </div>
          <div class="pd-position-badge" style="color:${positionConfig.color};background:${positionConfig.background};">${positionAbbrev}</div>
          <div class="pd-divider"></div>
          <div class="pd-bio-stats">
            <div class="pd-bio-row"><span class="pd-bio-label">Year</span><span class="pd-bio-value">${year}</span></div>
            <div class="pd-bio-row"><span class="pd-bio-label">Height</span><span class="pd-bio-value">${height}</span></div>
            <div class="pd-bio-row"><span class="pd-bio-label">Weight</span><span class="pd-bio-value">${weightValue} lbs</span></div>
          </div>
          <div class="pd-divider"></div>
          <div class="pd-status-label">STATUS</div>
          <div class="pd-status-grid">
            <div class="pd-status-cell">
              <div class="pd-status-cell-label">ATTITUDE</div>
              <div class="pd-status-emoji">${emotionEmoji}</div>
            </div>
            <div class="pd-status-cell">
              <div class="pd-status-cell-label">MOMENTUM</div>
              <div class="pd-status-value">${momentumValue}</div>
            </div>
          </div>
        </aside>

        <div class="pd-right-column">
          <section class="pd-section">
            <div class="pd-section-header">ATTRIBUTES</div>
            <div id="pd-attributes-grid" class="pd-attributes-grid"></div>
          </section>

          <section class="pd-section">
            <div class="pd-section-header">SCOUTING REPORT</div>
            <div class="pd-scouting-body">
              <div class="pd-placeholder">In Development</div>
            </div>
          </section>

          <section class="pd-section">
            <div class="pd-section-header">CAREER STATS</div>
            <div class="pd-table-wrap">
              <table class="pd-career-table">
                <thead>
                  <tr>
                    <th>Season</th>
                    <th>Team</th>
                    <th>GP</th>
                    <th>PTS</th>
                    <th>REB</th>
                    <th>AST</th>
                    <th>STL</th>
                    <th>BLK</th>
                    <th>FG%</th>
                    <th>3P%</th>
                  </tr>
                </thead>
                <tbody id="pd-career-stats-body"></tbody>
              </table>
            </div>
          </section>
        </div>
      </div>
    `;

    const backBtn = document.getElementById('pd-back-btn');
    if (backBtn) backBtn.addEventListener('click', goBack);

    renderAttributes(attributes);
    renderCareerStats(player, team, teamPrimaryColor);
    animateAttributeBars();

    if (typeof initAttributeTooltips !== 'undefined') {
      setTimeout(() => {
        initAttributeTooltips(document, ['.attribute-label']);
      }, 500);
    }
  }

  async function loadPlayerData() {
    const params = new URLSearchParams(window.location.search);
    const playerId = params.get('id');
    const mode = params.get('mode');
    const franchiseId = params.get('franchise_id');
    const tournamentId = params.get('tournament_id');
    const gameId = params.get('game_id');

    if (!playerId) {
      showError('No player ID provided');
      return;
    }

    try {
      const qs = new URLSearchParams();
      if (mode) qs.set('mode', mode);
      if (franchiseId) qs.set('franchise_id', franchiseId);
      if (tournamentId) qs.set('tournament_id', tournamentId);
      if (gameId) qs.set('game_id', gameId);

      const apiUrl = API_CONFIG.buildUrl(`/player/${encodeURIComponent(playerId)}`);
      const response = await fetch(qs.toString() ? `${apiUrl}?${qs.toString()}` : apiUrl);

      if (!response.ok) {
        throw new Error(`Failed to load player: ${response.statusText}`);
      }

      const player = await response.json();
      console.log('Player data loaded:', player);

      renderPlayerPage(player);
    } catch (error) {
      console.error('Error loading player:', error);
      showError(`Failed to load player data: ${error.message}`);
    }
  }

  window.goBack = goBack;
  window.normalizeTeamName = normalizeTeamName;
  window.getTeamBackground = getTeamBackground;
  window.getTeamLogo = getTeamLogo;
  window.normalizePhotoUrl = normalizePhotoUrl;
  window.formatHeight = formatHeight;
  window.formatYear = formatYear;

  window.addEventListener('DOMContentLoaded', () => {
    loadPlayerData();
  });
})();
