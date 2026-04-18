function playSound(filename) {
  try {
    var a = new Audio('/sounds/' + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function () {});
  } catch (e) {}
}

const ALPHA_DISMISS_STORAGE_KEY = 'alpha_disclaimer_dismissed_v1';
const COMMUNITY_LEADERBOARD_PLACEHOLDER = [
  { rank: 1, username: 'Coach Atlas', geek_points: 100, is_current_user: false },
  { rank: 2, username: 'Halfcourt Hero', geek_points: 94, is_current_user: false },
  { rank: 3, username: 'ZoneBreaker22', geek_points: 90, is_current_user: false },
  { rank: 4, username: 'Baseline Jamie', geek_points: 86, is_current_user: false },
  { rank: 5, username: 'Coach Carter', geek_points: 83, is_current_user: false },
  { rank: 6, username: 'GlassCleaner', geek_points: 81, is_current_user: false },
  { rank: 7, username: 'ScoutTape', geek_points: 78, is_current_user: false },
  { rank: 8, username: 'TempoSmith', geek_points: 74, is_current_user: false },
  { rank: 9, username: 'OrangeClipboard', geek_points: 71, is_current_user: false },
  { rank: 10, username: 'PressBreaker', geek_points: 68, is_current_user: false }
];

const franchisePlayNowBtn = document.getElementById('franchise-play-now-btn');
const franchiseNewBtn = document.getElementById('franchise-new-btn');
const franchiseDeleteLink = document.getElementById('franchise-delete-link');
const franchiseEmptyCard = document.getElementById('franchise-empty-card');
const franchiseCardBanner = document.getElementById('franchise-card-banner');
const franchiseCardSeasonProgress = document.getElementById('franchise-card-season-progress');
const franchiseCardRecord = document.getElementById('franchise-card-record');
const franchiseCardRank = document.getElementById('franchise-card-rank');
const franchiseCardPrestige = document.getElementById('franchise-card-prestige');
const franchiseCardNext = document.getElementById('franchise-card-next');
const franchiseCardCareerSummary = document.getElementById('franchise-card-career-summary');
const franchiseEnterBtn = document.getElementById('franchise-enter-btn');
const alphaDisclaimer = document.getElementById('alpha-disclaimer');
const alphaDisclaimerDismiss = document.getElementById('alpha-disclaimer-dismiss');
const leaderboardHost = document.getElementById('community-leaderboard');

let currentFranchise = null;

// Team name → square logo filename prefix (from images/square-logos/{code}_square.png)
const TEAM_LOGO_CODE = {
  'Bentley-Truman': 'bt',
  'Four Corners': 'fc',
  'Four-Corners': 'fc',
  'Lancaster': 'lan',
  'Little York': 'ly',
  'Little-York': 'ly',
  'Morristown': 'mor',
  'Ocean City': 'oc',
  'Ocean-City': 'oc',
  'South Lancaster': 'sl',
  'South-Lancaster': 'sl',
  'Xavien': 'xav'
};

function getSquareLogoPath(teamName) {
  if (typeof getTeamAssetPath === 'function') return getTeamAssetPath(teamName, 'banner_primary');
  return '/images/teams/general/general_banner_primary.jpg';
}

function clearFranchiseLocalStorage() {
  if (typeof localStorage === 'undefined') return;
  const toRemove = [
    'franchiseId',
    'franchise_id',
    'franchise_week',
    'franchise_user_team',
    'franchise_user_team_id',
  ];
  toRemove.forEach((k) => localStorage.removeItem(k));
  Object.keys(localStorage).forEach((k) => {
    if (k.startsWith('playbooks_position_filters_franchise_')) localStorage.removeItem(k);
  });
  localStorage.removeItem('last_game_id');
  localStorage.removeItem('last_box_score_gameId');
  localStorage.removeItem('last_box_score_url');
  localStorage.removeItem('last_game_user_team_side');
  localStorage.removeItem('game_home');
  localStorage.removeItem('game_away');
}

function getAuthHeaders() {
  try {
    return API_CONFIG.getAuthHeaders();
  } catch (e) {
    return {};
  }
}

function safeJsonFetch(url, options) {
  return fetch(url, options)
    .then(function (response) {
      if (!response.ok) return null;
      return response.json();
    })
    .catch(function () {
      return null;
    });
}

function safeText(value, fallback) {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function safeNumber(value, fallback) {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function deriveCurrentSeason(commandCenterData) {
  return safeNumber(commandCenterData && commandCenterData.current_season, 1);
}

function deriveRank(teamDoc, commandCenterData) {
  if (teamDoc) {
    const teamRank = teamDoc.natl_rank || teamDoc.rank || teamDoc.national_rank;
    if (teamRank !== undefined && teamRank !== null && String(teamRank).trim() !== '') {
      return String(teamRank);
    }
  }
  if (commandCenterData && commandCenterData.rank !== undefined && commandCenterData.rank !== null && commandCenterData.rank !== '-') {
    return String(commandCenterData.rank);
  }
  return '-';
}

function derivePrestige(teamDoc, commandCenterData) {
  if (commandCenterData && commandCenterData.prestige !== undefined && commandCenterData.prestige !== null && String(commandCenterData.prestige).trim() !== '') {
    return String(commandCenterData.prestige);
  }
  if (teamDoc && teamDoc.prestige !== undefined && teamDoc.prestige !== null && String(teamDoc.prestige).trim() !== '') {
    return String(teamDoc.prestige);
  }
  return '-';
}

function deriveRecord(commandCenterData, teamName) {
  const rankings = (commandCenterData && Array.isArray(commandCenterData.rankings)) ? commandCenterData.rankings : [];
  const teamEntry = rankings.find(function (entry) {
    return entry && entry.team_name === teamName;
  });
  if (!teamEntry) return '0-0';
  const wins = Number.isFinite(teamEntry.W) ? teamEntry.W : parseInt(teamEntry.W || 0, 10) || 0;
  const losses = Number.isFinite(teamEntry.L) ? teamEntry.L : parseInt(teamEntry.L || 0, 10) || 0;
  return wins + '-' + losses;
}

function deriveNextOpponent(commandCenterData, teamName) {
  const rankings = (commandCenterData && Array.isArray(commandCenterData.rankings)) ? commandCenterData.rankings : [];
  const teamEntry = rankings.find(function (entry) {
    return entry && entry.team_name === teamName;
  });
  if (!teamEntry) return 'TBD';
  return safeText(teamEntry.next, 'TBD');
}

function deriveSeasonProgress(commandCenterData, franchiseData) {
  const currentSeason = deriveCurrentSeason(commandCenterData);
  const week = safeNumber(franchiseData && franchiseData.week, 1);
  return 'Season ' + currentSeason + ' · Week ' + week + ' of 26';
}

function renderCareerSummary(commandCenterData) {
  if (!franchiseCardCareerSummary) return;
  const seasonCount = safeNumber(commandCenterData && commandCenterData.seasons_coached, deriveCurrentSeason(commandCenterData));
  const careerBestRankRaw = commandCenterData && commandCenterData.career_best_rank;
  const careerBestRank = (careerBestRankRaw !== undefined && careerBestRankRaw !== null && String(careerBestRankRaw).trim() !== '')
    ? String(careerBestRankRaw)
    : '--';
  franchiseCardCareerSummary.textContent = 'Season ' + seasonCount + ' · Career Best: #' + careerBestRank;
}

function renderCommunityLeaderboard(currentUsername) {
  if (!leaderboardHost) return;
  const currentUserNormalized = safeText(currentUsername, '').toLowerCase();
  let entries = COMMUNITY_LEADERBOARD_PLACEHOLDER.slice();
  if (currentUserNormalized && !entries.some(function (entry) { return entry.username.toLowerCase() === currentUserNormalized; })) {
    entries = entries.slice(0, 9).concat([{
      rank: 10,
      username: currentUsername,
      geek_points: 63,
      is_current_user: true
    }]);
  }
  const rows = entries.map(function (entry) {
    const isCurrent = entry.is_current_user || (currentUserNormalized && entry.username.toLowerCase() === currentUserNormalized);
    return `
      <div class="community-leaderboard-row${isCurrent ? ' is-current-user' : ''}">
        <div class="community-rank">${entry.rank}.</div>
        <div class="community-username">${entry.username}</div>
        <div class="community-score">${entry.geek_points}</div>
      </div>
    `;
  }).join('');
  leaderboardHost.innerHTML = rows || '<div class="community-leaderboard-empty">Leaderboard coming soon</div>';
}

function wireAlphaBanner() {
  if (!alphaDisclaimer || !alphaDisclaimerDismiss) return;
  alphaDisclaimerDismiss.addEventListener('click', function () {
    try {
      localStorage.setItem(ALPHA_DISMISS_STORAGE_KEY, '1');
    } catch (e) {}
    alphaDisclaimer.classList.add('is-dismissing');
    window.setTimeout(function () {
      alphaDisclaimer.classList.remove('visible', 'is-dismissing');
      alphaDisclaimer.hidden = true;
    }, 180);
  });
}

function renderFranchiseEmptyState() {
  if (franchiseEmptyCard) franchiseEmptyCard.style.display = 'block';
  if (franchisePlayNowBtn) franchisePlayNowBtn.style.display = 'none';
  if (franchiseDeleteLink) franchiseDeleteLink.style.display = 'none';
}

function renderFranchiseActiveState(franchiseData, teamDoc, commandCenterData) {
  if (!franchisePlayNowBtn) return;

  const teamName = safeText(franchiseData.user_team_id, 'Program');
  if (franchiseCardBanner) {
    franchiseCardBanner.src = getSquareLogoPath(teamName);
    franchiseCardBanner.alt = teamName;
  }
  if (franchiseCardSeasonProgress) franchiseCardSeasonProgress.textContent = deriveSeasonProgress(commandCenterData, franchiseData);
  if (franchiseCardRecord) franchiseCardRecord.textContent = deriveRecord(commandCenterData, teamName);
  if (franchiseCardRank) franchiseCardRank.textContent = deriveRank(teamDoc, commandCenterData);
  if (franchiseCardPrestige) franchiseCardPrestige.textContent = derivePrestige(teamDoc, commandCenterData);
  if (franchiseCardNext) franchiseCardNext.textContent = deriveNextOpponent(commandCenterData, teamName);
  renderCareerSummary(commandCenterData);

  if (franchiseEmptyCard) franchiseEmptyCard.style.display = 'none';
  franchisePlayNowBtn.style.display = 'block';
  if (franchiseDeleteLink) franchiseDeleteLink.style.display = 'inline';
}

function goToFranchiseCommandCenter() {
  if (currentFranchise && currentFranchise.franchise_id) {
    window.location.href = './franchise-command-center.html?franchise_id=' + encodeURIComponent(currentFranchise.franchise_id);
  } else {
    window.location.href = './franchise-select-team.html';
  }
}

const newFranchiseModal = document.getElementById('new-franchise-modal');
const newFranchiseDontShowAgain = document.getElementById('new-franchise-dont-show-again');
const newFranchiseModalCancel = document.getElementById('new-franchise-modal-cancel');
const newFranchiseModalConfirm = document.getElementById('new-franchise-modal-confirm');
const DONT_SHOW_NEW_FRANCHISE_WARNING_KEY = 'gob_dont_show_new_franchise_warning';

function openNewFranchiseModal() {
  if (newFranchiseModal) newFranchiseModal.style.display = 'flex';
}

function closeNewFranchiseModal() {
  if (newFranchiseModal) newFranchiseModal.style.display = 'none';
}

function goToNewFranchise() {
  window.location.href = './franchise-select-team.html';
}

async function startNewFranchiseFlow() {
  playSound('click-beep.wav');
  const dontShow = typeof localStorage !== 'undefined' && localStorage.getItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY) === '1';
  const hasExistingFranchise = !!currentFranchise;
  if (hasExistingFranchise && !dontShow) {
    openNewFranchiseModal();
    return;
  }
  if (hasExistingFranchise && dontShow) {
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/delete-current'), {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (res.ok) clearFranchiseLocalStorage();
    } catch (e) {
      console.warn('[mode-select] delete-current franchise (dontShow path):', e);
    }
  }
  goToNewFranchise();
}

if (franchisePlayNowBtn) {
  franchisePlayNowBtn.addEventListener('click', function () {
    playSound('click-strong.wav');
    goToFranchiseCommandCenter();
  });
  franchisePlayNowBtn.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      playSound('click-strong.wav');
      goToFranchiseCommandCenter();
    }
  });
}

if (franchiseEnterBtn) {
  franchiseEnterBtn.addEventListener('click', function (event) {
    event.stopPropagation();
    playSound('click-strong.wav');
    goToFranchiseCommandCenter();
  });
}

if (franchiseNewBtn) {
  franchiseNewBtn.addEventListener('click', startNewFranchiseFlow);
}

if (franchiseDeleteLink) {
  franchiseDeleteLink.addEventListener('click', startNewFranchiseFlow);
}

if (newFranchiseModalCancel) {
  newFranchiseModalCancel.addEventListener('click', closeNewFranchiseModal);
}

if (newFranchiseModalConfirm) {
  newFranchiseModalConfirm.addEventListener('click', async function () {
    if (newFranchiseDontShowAgain && newFranchiseDontShowAgain.checked && typeof localStorage !== 'undefined') {
      localStorage.setItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY, '1');
    }
    closeNewFranchiseModal();
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/delete-current'), {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        console.warn('[mode-select] delete-current franchise failed:', res.status);
      } else {
        clearFranchiseLocalStorage();
      }
    } catch (e) {
      console.warn('[mode-select] delete-current franchise error:', e);
    }
    goToNewFranchise();
  });
}

document.addEventListener('DOMContentLoaded', async function () {
  try {
    const lobbyMusic = new Audio('/sounds/crossover-21738.mp3');
    lobbyMusic.loop = true;
    lobbyMusic.volume = 0.4;
    lobbyMusic.play().catch(function () {});
  } catch (e) {}

  try {
    const appConfig = await API_CONFIG.loadAppConfig();
    if (appConfig.isAlpha) {
      const alphaBadge = document.getElementById('alpha-badge');
      const isDismissed = typeof localStorage !== 'undefined' && localStorage.getItem(ALPHA_DISMISS_STORAGE_KEY) === '1';
      if (alphaBadge) alphaBadge.classList.add('visible');
      if (alphaDisclaimer && !isDismissed) {
        alphaDisclaimer.hidden = false;
        alphaDisclaimer.classList.add('visible');
      }
      console.log('[ALPHA] Alpha mode enabled');
    }
  } catch (error) {
    console.error('[ALPHA] Failed to load app config:', error);
  }

  const authLoggedOut = document.getElementById('auth-logged-out');
  const authLoggedIn = document.getElementById('auth-logged-in');
  const authUserEmail = document.getElementById('auth-user-email');
  const logoutBtn = document.getElementById('logout-btn');
  const authToken = localStorage.getItem('auth_token');
  const authUser = localStorage.getItem('auth_user');
  let currentUsername = '';

  wireAlphaBanner();

  if (authToken && authUser) {
    try {
      const user = JSON.parse(authUser);
      currentUsername = user.username || user.email || '';
      if (authLoggedOut) authLoggedOut.style.display = 'none';
      if (authLoggedIn) authLoggedIn.style.display = 'flex';
      if (authUserEmail) authUserEmail.textContent = user.username || user.email;

      const meRes = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: getAuthHeaders() });
      if (meRes.ok) {
        const meData = await meRes.json();
        if (meData.username && meData.username.trim()) {
          currentUsername = meData.username;
          if (authUserEmail) authUserEmail.textContent = meData.username;
          const stored = JSON.parse(authUser);
          stored.username = meData.username;
          localStorage.setItem('auth_user', JSON.stringify(stored));
        }
      } else if (meRes.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        if (authLoggedOut) authLoggedOut.style.display = 'flex';
        if (authLoggedIn) authLoggedIn.style.display = 'none';
      }
    } catch (e) {
      console.error('[AUTH] Failed to parse user:', e);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      if (authLoggedOut) authLoggedOut.style.display = 'flex';
      if (authLoggedIn) authLoggedIn.style.display = 'none';
    }
  }

  renderCommunityLeaderboard(currentUsername);

  if (logoutBtn) {
    logoutBtn.addEventListener('click', async function () {
      try {
        await fetch(API_CONFIG.buildUrl('/api/auth/logout'), { method: 'POST' });
      } catch (e) {}
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      if (authLoggedOut) authLoggedOut.style.display = 'flex';
      if (authLoggedIn) authLoggedIn.style.display = 'none';
    });
  }

  const headers = getAuthHeaders();
  const currentFranchiseData = await safeJsonFetch(API_CONFIG.buildUrl('/franchise/current'), { headers: headers });
  currentFranchise = currentFranchiseData;

  const teamsData = await safeJsonFetch(API_CONFIG.buildUrl('/teams'), { headers: headers }) || [];
  const teamsByName = {};
  teamsData.forEach(function (team) {
    if (team && team.name) teamsByName[team.name] = team;
  });

  if (!currentFranchise) {
    renderFranchiseEmptyState();
    return;
  }

  const commandCenterData = await safeJsonFetch(
    API_CONFIG.buildUrl('/franchise/command-center/data?franchise_id=' + encodeURIComponent(currentFranchise.franchise_id)),
    { headers: headers }
  );

  const teamName = safeText(currentFranchise.user_team_id, '');
  const teamDoc = teamsByName[teamName] || null;
  renderFranchiseActiveState(currentFranchise, teamDoc, commandCenterData);
});
