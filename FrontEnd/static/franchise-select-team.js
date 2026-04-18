function playSound(filename) {
  try {
    var a = new Audio("/sounds/" + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function () {});
  } catch (e) {}
}

const teams = [
  "Bentley-Truman",
  "Lancaster",
  "Four Corners",
  "Ocean City",
  "Morristown",
  "Little York",
  "Xavien",
  "South Lancaster"
];

const taglines = {
  'Bentley-Truman': 'Top-Shelf Talent',
  'Lancaster': 'Muscle & Defense',
  'Four Corners': 'Hustle & Attitude',
  'Ocean City': 'Sharpshooters Galore',
  'Morristown': 'Perfectly Balanced',
  'Little York': 'Wicked Smart',
  'Xavien': 'Youthful Exuberance',
  'South Lancaster': 'Us vs The World'
};

const teamContainer = document.getElementById("team-container");
const errorHost = document.getElementById("team-select-error");
const loadingOverlay = document.getElementById("team-select-loading");
const loadingBanner = document.getElementById("team-select-loading-banner");
const loadingSubline = document.getElementById("team-select-loading-subline");
const backLink = document.getElementById("team-select-back-link");

function buildReturnUrl() {
  return window.location.pathname + window.location.search;
}

function hideError() {
  if (!errorHost) return;
  errorHost.hidden = true;
  errorHost.textContent = "";
}

function showError(message) {
  if (!errorHost) return;
  errorHost.textContent = message;
  errorHost.hidden = false;
}

function showLoading(team) {
  if (!loadingOverlay || !loadingBanner || !loadingSubline) return;
  loadingBanner.src = typeof getTeamAssetPath === 'function'
    ? getTeamAssetPath(team, 'banner_primary')
    : '/images/teams/general/general_banner_primary.jpg';
  loadingBanner.alt = team;
  loadingSubline.textContent = 'Getting ' + team + ' ready for the season...';
  loadingOverlay.hidden = false;
}

function hideLoading() {
  if (loadingOverlay) loadingOverlay.hidden = true;
}

function createButtons() {
  if (!teamContainer) return;
  teams.forEach(team => {
    const card = document.createElement("div");
    card.className = "team-card";
    card.innerHTML = `
      <div class="team-card-banner">
        <img src="${typeof getTeamAssetPath === 'function' ? getTeamAssetPath(team, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg'}" alt="${team}">
        <div class="team-card-tagline">${taglines[team] || team}</div>
        <div class="team-card-overlay">
          <button class="team-card-action team-card-action-scout" type="button">Scout</button>
          <button class="team-card-action team-card-action-select" type="button">Select</button>
        </div>
      </div>
    `;
    const scoutBtn = card.querySelector(".team-card-action-scout");
    const selectBtn = card.querySelector(".team-card-action-select");
    if (scoutBtn) {
      scoutBtn.addEventListener("click", () => {
        playSound("click-beep.wav");
        window.location.href = '/team-roster-view.html?team_name=' + encodeURIComponent(team) + '&return_url=' + encodeURIComponent(buildReturnUrl());
      });
    }
    if (selectBtn) {
      selectBtn.addEventListener("click", () => {
        playSound("click-beep.wav");
        selectTeam(team);
      });
    }
    teamContainer.appendChild(card);
  });
}

async function selectTeam(team) {
  hideError();
  showLoading(team);
  try {
    const headers = { ...API_CONFIG.getAuthHeaders(), "Content-Type": "application/json" };
    const res = await fetch(API_CONFIG.buildUrl('/franchise/select-team?profile=1'), {
      method: "POST",
      headers,
      body: JSON.stringify({ team_name: team })
    });
    if (!res.ok) {
      let msg = "Unable to start franchise";
      try {
        const errBody = await res.json();
        if (errBody.detail) msg = errBody.detail;
      } catch (_) {}
      throw new Error(msg);
    }
    const data = await res.json();
    localStorage.setItem("franchiseId", data.franchise_id);
    localStorage.setItem("franchise_user_team", team);
    window.location.href = `./franchise-command-center.html?franchise_id=${encodeURIComponent(data.franchise_id)}`;
  } catch (err) {
    console.error(err);
    hideLoading();
    showError(err.message || "Unable to start franchise");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  // Looping lobby music on franchise team-select screen
  try {
    var lobbyMusic = new Audio("/sounds/crossover-21738.mp3");
    lobbyMusic.loop = true;
    lobbyMusic.volume = 0.4;
    lobbyMusic.play().catch(function () {});
  } catch (e) {}
  if (backLink) {
    backLink.addEventListener("click", function (event) {
      event.preventDefault();
      window.location.href = '/mode-select.html';
    });
  }
  createButtons();
});
