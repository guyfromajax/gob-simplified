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

  function getPositionRatings(player) {
    // TODO: confirm position ratings field name against actual player model
    if (player?.position_ratings && typeof player.position_ratings === 'object') {
      return player.position_ratings;
    }

    const keys = ['PG', 'SG', 'SF', 'PF', 'C'];
    const fromFields = {};
    keys.forEach((position) => {
      const value = player?.[`rt_${position.toLowerCase()}`] ?? player?.[`RT_${position}`] ?? null;
      if (value !== null && value !== undefined) {
        fromFields[position] = value;
      }
    });
    if (Object.keys(fromFields).length) {
      return fromFields;
    }

    return null;
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
    const colorBucket = Math.max(0, Math.ceil(Number(rawValue) / 10));
    const row = document.createElement('div');
    row.className = 'pd-attribute-row';
    row.innerHTML = `
      <span class="pd-attribute-label attribute-label" data-attr="${code}">${code}</span>
      <div class="pd-attribute-track">
        <div class="pd-attribute-fill" data-width="${fillPercentage}" style="background:${getAttrColor(colorBucket)};"></div>
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

  function animatePositionRatings() {
    const bars = document.querySelectorAll('.pd-pos-bar-fill');
    bars.forEach((bar, index) => {
      setTimeout(() => {
        const targetWidth = bar.getAttribute('data-width') || '0';
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
    if (typeof GOB_PlayerYear !== 'undefined' && GOB_PlayerYear.formatDisplay) {
      return GOB_PlayerYear.formatDisplay(year);
    }
    if (!year) return 'N/A';
    const yearStr = String(year).toLowerCase();
    const yearMap = {
      senior: 'SR',
      junior: 'JR',
      sophomore: 'SO',
      freshman: 'FR',
      sr: 'SR',
      jr: 'JR',
      so: 'SO',
      fr: 'FR',
      jh: 'JH',
      graduate: 'GR',
      grad: 'GR',
    };
    return yearMap[yearStr] || (yearStr ? yearStr.toUpperCase() : 'N/A');
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

  function getPortraitBackground(player, staticPrefix = '') {
    const isUnsignedRecruit = !!player?.is_recruit && !player?.is_signed;
    if (isUnsignedRecruit) {
      return {
        className: 'pd-portrait-wrap--unsigned-recruit',
        style: '',
      };
    }

    // A signed FRD record has not necessarily been converted into a player yet,
    // so its assigned school lives at signed_team_name rather than team.
    const teamName = normalizeTeamName(
      (player?.is_recruit && player?.is_signed ? player?.signed_team_name : null)
      || player?.team
      || 'Free Agent'
    );
    const background = getTeamBackground(teamName, staticPrefix);
    return {
      className: '',
      style: `background-image:url('${background}');background-size:cover;background-position:center;`,
    };
  }

  function goBack() {
    const params = new URLSearchParams(window.location.search);
    // Same-origin guard: return_url is attacker-controllable via the query string.
    const returnUrl = typeof getSafeReturnUrl === 'function'
      ? getSafeReturnUrl(params.get('return_url'))
      : params.get('return_url');
    if (returnUrl) {
      window.location.href = returnUrl;
      return;
    }

    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = '/homepage.html';
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
    const formatWholeDefPct = (made, attempts) => attempts > 0 ? `${Math.round((made / attempts) * 100)}%` : '0%';

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
      <td class="pd-career-num">${formatWholeDefPct(defS, defA)}</td>
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

  function renderPositionRatingsBlock(player, primaryPosition) {
    const ratings = getPositionRatings(player);
    if (!ratings) return '';

    const order = ['PG', 'SG', 'SF', 'PF', 'C'];
    const rows = order.map((position) => {
      const rawValue = ratings[position];
      const rating = Number(rawValue);
      const safeRating = Number.isFinite(rating) ? rating : 0;
      const posConfig = getPositionConfig(position);
      const isPrimary = position === primaryPosition;
      const opacity = isPrimary ? 1 : 0.7;

      return `
        <div class="pd-pos-rating-row" style="opacity:${opacity};">
          <div class="pd-pos-pill" style="background:${posConfig.background};color:${posConfig.color};">${position}</div>
          <div class="pd-pos-bar-track">
            <div class="pd-pos-bar-fill" data-width="${Math.min(100, safeRating)}" style="background:${getRtColor(safeRating)};width:0;"></div>
          </div>
          <div class="pd-pos-rating-value ${isPrimary ? 'is-primary' : ''}">${Number.isFinite(rating) ? formatRtDisplay(rating) : '--'}</div>
        </div>
      `;
    }).join('');

    return `<div class="pd-position-ratings">${rows}</div>`;
  }

  /**
   * Un-signed recruit portrait: the white master keyed by image_id. Painted
   * lazily, so a 404 means "not painted yet" — ensure, retry once cache-busted,
   * then fall back to generic. Wired imperatively (not via buildPortrait's
   * inline onerror) because the retry is async.
   */
  function buildRecruitPortrait(fullName) {
    return `<img alt="${escapeAttr(fullName)}" class="pd-portrait" id="pd-recruit-portrait">`;
  }

  function wireRecruitPortrait(imageId) {
    const img = document.getElementById('pd-recruit-portrait');
    if (!img) return;
    const api = window.API_CONFIG;
    const url = api.getRecruitImageUrl(imageId, { size: 'modal' });
    const generic = api.getGenericHeadshotUrl({ size: 'modal' });
    img.onerror = () => {
      api.ensureRecruitImage(imageId).then(() => {
        img.onerror = () => { img.onerror = null; img.src = generic; };
        img.src = api.getRecruitImageUrl(imageId, { size: 'modal' }) + '?r=1';
      });
    };
    img.src = url;
  }

  /**
   * Signed-player portrait: the UNIFORMED master keyed by player_id. Just like
   * the recruit portrait it's painted lazily, so a 404 on the master means "not
   * painted yet" — ensure (which recolors the recruit's kit into the team's
   * uniform), retry once cache-busted, then fall back to generic. Only used for
   * players that carry an image_id (signed recruits / dynamic recruits); league
   * players keep buildPortrait's pre-existing-master cascade.
   */
  function buildSignedPlayerPortrait(fullName) {
    return `<img alt="${escapeAttr(fullName)}" class="pd-portrait" id="pd-player-portrait">`;
  }

  function wireSignedPlayerPortrait(playerId) {
    const img = document.getElementById('pd-player-portrait');
    if (!img) return;
    const api = window.API_CONFIG;
    const franchiseId = new URLSearchParams(window.location.search).get('franchise_id');
    const url = api.getPlayerImageUrl(playerId, { size: 'modal' });
    const generic = api.getGenericHeadshotUrl({ size: 'modal' });
    img.onerror = () => {
      api.ensurePlayerImage(franchiseId, playerId).then(() => {
        img.onerror = () => { img.onerror = null; img.src = generic; };
        img.src = api.getPlayerImageUrl(playerId, { size: 'modal' }) + '?r=1';
      });
    };
    img.src = url;
  }

  function escapeAttr(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function buildPortrait(photo, fullName, genericPhoto, fallbackPhoto) {
    if (!photo) {
      return '<div class="pd-portrait-placeholder" aria-hidden="true"></div>';
    }
    const initialFallbackState = photo === fallbackPhoto ? 'player' : 'primary';
    return `<img src="${photo}" alt="${escapeAttr(fullName)}" class="pd-portrait" onerror="if(this.dataset.fallbackState==='generic'){this.remove();this.parentElement.innerHTML='<div class=&quot;pd-portrait-placeholder&quot; aria-hidden=&quot;true&quot;></div>';}else if(this.dataset.fallbackState==='player'){this.dataset.fallbackState='generic';this.src='${genericPhoto}';}else{this.dataset.fallbackState='player';this.src='${fallbackPhoto}';}" data-fallback-state="${initialFallbackState}">`;
  }

  /**
   * Recruit-only block. Home Region / Lean / archetype exist on FRD docs but
   * never on players, and fill the space where STATUS sits for a player.
   * `Lean` is a {"1","2","3"} -> team_id ranking; only the top choice is shown.
   * After week-35 recruiting runs, LEAN is replaced by SIGNED (school name).
   */
  function buildRecruitingBlock(player) {
    const leanOrSigned = player.is_signed
      ? ['SIGNED', player.signed_display || player.signed_team_name || '--']
      : ['LEAN', player.lean_display || '--'];
    const rows = [
      ['ARCHETYPE', player.archetype || '--'],
      ['HOME REGION', player['Home Region'] || '--'],
      leanOrSigned,
    ];
    return `
      <div class="pd-divider"></div>
      <div class="pd-status-label">RECRUITING</div>
      <div class="pd-recruiting-grid">
        ${rows.map(([label, value]) => `
          <div class="pd-recruiting-row">
            <span class="pd-recruiting-label">${label}</span>
            <span class="pd-recruiting-value">${escapeAttr(value)}</span>
          </div>
        `).join('')}
      </div>
    `;
  }

  function formatScoutingReport(player) {
    const raw = player?.scouting_report;
    if (typeof raw !== 'string' || !raw.trim()) {
      return '<p class="pd-scouting-empty">No scouting report available.</p>';
    }
    const escaped = raw
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/\n/g, '<br>');
    return `<p class="pd-scouting-text">${escaped}</p>`;
  }

  function renderPlayerPage(player) {
    const content = document.getElementById('pd-content');
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const staticPrefix = isLocalhost ? '/static' : '';

    const isRecruit = !!player.is_recruit;
    const firstName = player.first_name || '';
    const lastName = player.last_name || '';
    // Recruits carry a single `name`; players carry first_name/last_name.
    const fullName = `${firstName} ${lastName}`.trim() || player.name || 'Unknown Player';
    const rawTeam = (isRecruit && player.is_signed ? player.signed_team_name : null)
      || player.team
      || 'Free Agent';
    const team = normalizeTeamName(rawTeam);
    const heightValue = player.height || player.HT || 75;
    const height = formatHeight(heightValue);
    const weightValue = player.weight || player.WT || '--';
    const jersey = (typeof player.jersey === 'number') ? player.jersey : (player.jersey !== undefined && player.jersey !== null && player.jersey !== '' ? player.jersey : '');
    const fallbackPhoto = window.API_CONFIG?.getPlayerImageUrl
      ? window.API_CONFIG.getPlayerImageUrl(player._id, { size: 'modal' })
      : `${staticPrefix}/images/players/${player._id}.png`;
    const genericPhoto = window.API_CONFIG?.getGenericHeadshotUrl
      ? window.API_CONFIG.getGenericHeadshotUrl({ size: 'modal' })
      : `${staticPrefix}/images/players/generic_headshot.png`;
    const photo = fallbackPhoto;
    // Signed recruits / dynamic recruits carry an image_id and their uniformed
    // master is painted lazily on first view — wire the ensure-on-404 flow for
    // them. League players (no image_id) keep the pre-existing-master cascade.
    const hasLazyMaster = !isRecruit && !!player.image_id;
    const attributes = player.attributes || {};
    const year = formatYear(player.year);
    const positionAbbrev = getHighestPosition(player);
    const positionConfig = getPositionConfig(positionAbbrev);
    const rtValue = getPlayerOverall(player);
    const momentumValue = getPlayerMomentum(player);
    const emotionEmoji = getEmotionEmoji(player);
    const portraitBackground = getPortraitBackground(player, staticPrefix);
    const teamPrimaryColor = player.primary_color || POSITION_CONFIG[positionAbbrev]?.color || '';
    const posConfig = getPositionConfig(positionAbbrev);
    const positionRatingsBlock = renderPositionRatingsBlock(player, positionAbbrev);
    const yearJerseyLine = jersey !== '' ? `${year} · #${jersey}` : year;
    const heightWeightLine = `${height} · ${weightValue} lbs`;

    content.innerHTML = `
      <div class="resource-page-container fcc-brand-page-shell pd-shell">
        <aside class="pd-left-card">
          <button class="pd-back-btn" id="pd-back-btn">Back</button>
          <div class="pd-portrait-wrap ${portraitBackground.className}" style="${portraitBackground.style}">
            ${isRecruit
              ? buildRecruitPortrait(fullName)
              : (hasLazyMaster
                  ? buildSignedPlayerPortrait(fullName)
                  : buildPortrait(photo, fullName, genericPhoto, fallbackPhoto))}
          </div>
          <div class="pd-player-name">${fullName}</div>
          <div class="pd-pos-line">${yearJerseyLine}</div>
          <div class="pd-pos-line">${heightWeightLine}</div>
          <div class="pd-overall">
            <div class="pd-overall-label">OVERALL</div>
            <div class="pd-overall-value">${formatRtDisplay(rtValue)}</div>
          </div>
          ${positionRatingsBlock}
          ${isRecruit ? buildRecruitingBlock(player) : `
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
          </div>`}
        </aside>

        <div class="pd-right-column">
          <section class="pd-section">
            <div class="pd-section-header">ATTRIBUTES</div>
            <div id="pd-attributes-grid" class="pd-attributes-grid"></div>
          </section>

          <section class="pd-section">
            <div class="pd-section-header">SCOUTING REPORT</div>
            <div class="pd-scouting-body">
              ${formatScoutingReport(player)}
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

    if (isRecruit) wireRecruitPortrait(player.image_id);
    else if (hasLazyMaster) wireSignedPlayerPortrait(player._id);

    renderAttributes(attributes);
    renderCareerStats(player, team, teamPrimaryColor);
    animateAttributeBars();
    animatePositionRatings();

    if (typeof initAttributeTooltips !== 'undefined') {
      setTimeout(() => {
        initAttributeTooltips(document, ['.attribute-label']);
      }, 500);
    }
  }

  async function loadRecruitData(recruitId, franchiseId) {
    if (!franchiseId) {
      showError('No franchise ID provided');
      return;
    }
    try {
      const apiUrl = API_CONFIG.buildUrl(`/recruit/${encodeURIComponent(recruitId)}`)
        + `?franchise_id=${encodeURIComponent(franchiseId)}`;
      const response = await fetch(apiUrl);
      if (!response.ok) {
        throw new Error(`Failed to load recruit: ${response.statusText}`);
      }
      renderPlayerPage(await response.json());
    } catch (error) {
      console.error('Error loading recruit:', error);
      showError(`Failed to load recruit data: ${error.message}`);
    }
  }

  async function loadPlayerData() {
    const params = new URLSearchParams(window.location.search);
    const playerId = params.get('id');
    const recruitId = params.get('recruit_id');
    const mode = params.get('mode');
    const franchiseId = params.get('franchise_id');
    const tournamentId = params.get('tournament_id');
    const gameId = params.get('game_id');

    // Recruit mode: un-signed recruits live in FRD, not the players collection.
    if (recruitId) {
      await loadRecruitData(recruitId, franchiseId);
      return;
    }

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
