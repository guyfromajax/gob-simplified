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
    const positionRatings = player?.position_ratings || {};
    const rankedPositions = Object.entries(positionRatings)
      .filter(([, value]) => Number.isFinite(Number(value)))
      .sort((a, b) => Number(b[1]) - Number(a[1]));
    if (rankedPositions.length) {
      return String(rankedPositions[0][0] || '--').toUpperCase();
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
    const body = document.getElementById('pd-stats-body');
    if (!body) return;
    body.innerHTML = '';
    const seasonStats = player?.season || player?.stats?.season || {};
    const stats = typeof seasonStats === 'object' && !Array.isArray(seasonStats) ? seasonStats : {};
    const tpm = Number(stats['3PTM'] || stats.TPM || 0);
    const tpa = Number(stats['3PTA'] || stats.TPA || 0);
    const fgm = Number(stats.FGM || 0);
    const fga = Number(stats.FGA || 0);
    const ftm = Number(stats.FTM || 0);
    const fta = Number(stats.FTA || 0);
    const dreb = Number(stats.DREB || 0);
    const oreb = Number(stats.OREB || 0);
    const treb = Number(stats.TREB || stats.REB || (dreb + oreb) || 0);
    const scrA = Number(stats.SCR_A || 0);
    const scrS = Number(stats.SCR_S || 0);
    const defA = Number(stats.DEF_A || 0);
    const defS = Number(stats.DEF_S || 0);
    const formatPct = (made, attempts) => attempts > 0 ? `${((made / attempts) * 100).toFixed(1)}%` : '0.0%';

    const tr = document.createElement('tr');
    tr.className = 'pd-current-season';
    tr.innerHTML = `
      <td class="pd-career-num">${stats.PTS ?? 0}</td>
      <td class="pd-career-num">${fgm}</td>
      <td class="pd-career-num">${fga}</td>
      <td class="pd-career-num">${formatPct(fgm, fga)}</td>
      <td class="pd-career-num">${tpm}</td>
      <td class="pd-career-num">${tpa}</td>
      <td class="pd-career-num">${formatPct(tpm, tpa)}</td>
      <td class="pd-career-num">${ftm}</td>
      <td class="pd-career-num">${fta}</td>
      <td class="pd-career-num">${formatPct(ftm, fta)}</td>
      <td class="pd-career-num">${dreb}</td>
      <td class="pd-career-num">${oreb}</td>
      <td class="pd-career-num">${treb}</td>
      <td class="pd-career-num">${stats.AST ?? 0}</td>
      <td class="pd-career-num">${stats.STL ?? 0}</td>
      <td class="pd-career-num">${stats.BLK ?? 0}</td>
      <td class="pd-career-num">${stats.F ?? 0}</td>
      <td class="pd-career-num">${stats.MIN ?? 0}</td>
      <td class="pd-career-num">${stats.TO ?? 0}</td>
      <td class="pd-career-num">${scrA}</td>
      <td class="pd-career-num">${formatPct(scrS, scrA)}</td>
      <td class="pd-career-num">${defA}</td>
      <td class="pd-career-num">${formatPct(defS, defA)}</td>
    `;
    body.appendChild(tr);
  }

  function getPlayerOverall(player) {
    const positionRatings = player?.position_ratings || {};
    const ratings = Object.values(positionRatings)
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));
    if (!ratings.length) {
      return player?.rt ?? player?.RT ?? '--';
    }
    return Math.max(...ratings);
  }

  function getPlayerMomentum(player) {
    const momentum = player?.attributes?.MO ?? player?.MO ?? player?.mo ?? player?.momentum;
    return momentum === undefined || momentum === null || momentum === '' ? '--' : momentum;
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
    const rtValue = getPlayerOverall(player);
    const momentumValue = getPlayerMomentum(player);
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
            <div class="pd-section-header">STATS</div>
            <div class="pd-table-wrap">
              <table class="pd-career-table">
                <thead>
                  <tr>
                    <th>PTS</th>
                    <th>FGM</th>
                    <th>FGA</th>
                    <th>FG%</th>
                    <th>3PTM</th>
                    <th>3PTA</th>
                    <th>3PT%</th>
                    <th>FTM</th>
                    <th>FTA</th>
                    <th>FT%</th>
                    <th>DREB</th>
                    <th>OREB</th>
                    <th>TREB</th>
                    <th>AST</th>
                    <th>STL</th>
                    <th>BLK</th>
                    <th>F</th>
                    <th>MIN</th>
                    <th>TO</th>
                    <th>SCRA</th>
                    <th>SCR%</th>
                    <th>DEFA</th>
                    <th>DEF%</th>
                  </tr>
                </thead>
                <tbody id="pd-stats-body"></tbody>
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
