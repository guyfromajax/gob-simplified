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

// FTE v2 tutorial branch: when ?mode=tutorial is present, this page is the
// first step of the new-user funnel rather than a franchise-creation entry.
const TUTORIAL_MODE = new URLSearchParams(window.location.search).get("mode") === "tutorial";

// Mascot map (team name → mascot string) loaded on demand from /teams.
// Single source of truth = team_doc.mascot in the teams collection. Used by
// the username modal copy ("you're now coaching the {mascot}, Coach"). Fired
// once at module load when in tutorial mode so the click handler can await
// without an extra round-trip mid-click.
let mascotMapPromise = null;
function fetchMascotMap() {
  if (mascotMapPromise) return mascotMapPromise;
  mascotMapPromise = fetch(API_CONFIG.buildUrl('/teams'), { headers: API_CONFIG.getAuthHeaders() })
    .then(res => res.ok ? res.json() : [])
    .then(teams => {
      const map = {};
      for (const t of teams || []) {
        if (t && t.name && t.mascot) map[t.name] = t.mascot;
      }
      return map;
    })
    .catch(err => {
      console.warn('[franchise-select-team] could not load mascots:', err);
      return {};
    });
  return mascotMapPromise;
}
if (TUTORIAL_MODE) {
  // Prefetch so the click handler's await is effectively free.
  fetchMascotMap();
}

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
    card.dataset.team = team;
    const overlayHtml = `<button class="team-card-action team-card-action-scout" type="button">Scout</button>
       <button class="team-card-action team-card-action-select" type="button">Select</button>`;
    const overlayClass = 'team-card-overlay';
    card.innerHTML = `
      <div class="team-card-check" aria-hidden="true">✓</div>
      <div class="team-card-banner">
        <img src="${typeof getTeamAssetPath === 'function' ? getTeamAssetPath(team, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg'}" alt="${team}">
        <div class="team-card-tagline">${taglines[team] || team}</div>
        <div class="${overlayClass}">
          ${overlayHtml}
        </div>
      </div>
    `;
    const scoutBtn = card.querySelector(".team-card-action-scout");
    const selectBtn = card.querySelector(".team-card-action-select");
    if (scoutBtn) {
      scoutBtn.addEventListener("click", () => {
        playSound("click-beep.wav");
        const scoutParams = new URLSearchParams();
        scoutParams.set('team_name', team);
        scoutParams.set('return_url', buildReturnUrl());
        // FTE v2 tutorial: carry mode=tutorial so authBarInit's routeToTutorial
        // treats team-roster-view as a shoulder page and doesn't bounce the
        // user back to the team-select step.
        if (TUTORIAL_MODE) scoutParams.set('mode', 'tutorial');
        window.location.href = '/team-roster-view.html?' + scoutParams.toString();
      });
    }
    if (selectBtn) {
      selectBtn.addEventListener("click", () => {
        playSound("click-beep.wav");
        if (TUTORIAL_MODE) {
          // Visually commit the selection so the choice feels registered
          // before the username modal opens. Clear prior selections so we
          // never end up with two highlighted cards if the user changes
          // their mind in the few hundred ms before the modal appears.
          if (teamContainer) {
            teamContainer.querySelectorAll('.team-card.is-selected').forEach(el => el.classList.remove('is-selected'));
          }
          card.classList.add('is-selected');
          selectTutorialTeam(team);
        } else {
          selectTeam(team);
        }
      });
    }
    teamContainer.appendChild(card);
  });
}

// FTE v2 tutorial flow: team selection records the pick in tutorial_state,
// opens the username modal with team-aware copy, and on submit routes to the
// situation card page. No franchise is created here — the tutorial game is
// throwaway (single mode behind the scenes).
async function selectTutorialTeam(team) {
  hideError();
  try {
    // Step 1: persist the team pick + advance tutorial_state to "username".
    const advanceRes = await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'username', team_pick: team }),
    });
    if (!advanceRes.ok) {
      throw new Error('Could not start tutorial');
    }
  } catch (err) {
    console.error('[tutorial] team-pick advance failed:', err);
    showError(err.message || 'Could not start tutorial');
    return;
  }

  // Step 2: open the username Functional modal with team-aware chrome.
  // Mascot drives the title ("YOU'RE COACHING THE STERLING KNIGHTS").
  // Team name drives the Sammy portrait variant (team-linked kit).
  const mascotMap = await fetchMascotMap();
  const mascot = mascotMap[team] || team;
  const { openUsernameModal } = await import('/js/shared/usernameModal.js');
  openUsernameModal({
    teamName: team,
    mascot,
    onSuccess: async () => {
      // Mask the team-select page during the in-flight nav to tutorial-situation
      // so the user doesn't see the (now-stale) team grid flash between modal
      // close and tutorial-situation's first paint. The destination page paints
      // its own dark backdrop + Moment modal as soon as its script runs, so no
      // further coordination is needed.
      if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
        window.PageLoadOverlay.show();
      }
      // Step 3: advance to "situation" and navigate to the situation card.
      try {
        await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
          method: 'POST',
          headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ step: 'situation' }),
        });
      } catch (e) {
        // Don't block the user on a non-critical step advance — the situation
        // page will be safe to re-enter and will see the prior step in state.
        console.warn('[tutorial] could not advance to situation step:', e);
      }
      window.location.href = '/tutorial-situation.html';
    },
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

  if (TUTORIAL_MODE) {
    // Tutorial flow: strict header + a single confident, low-stakes subhead.
    // No intro modal (Coach feedback: don't block team selection with a modal).
    if (backLink) backLink.style.display = 'none';
    const title = document.getElementById('page-title');
    const subtitle = document.getElementById('page-subtitle');
    if (title) title.textContent = 'Pick Your Program';
    if (subtitle) {
      subtitle.textContent = "This one's your onboarding — a single game to feel out the controls. Your real franchise comes next. Pick whoever speaks to you.";
    }
    // Mount the quiet 5-step progress thread (Pick Program = step 2 of 5).
    import('/js/shared/tutorialProgressThread.js')
      .then(({ mountTutorialProgress }) => mountTutorialProgress('program'))
      .catch((e) => console.warn('[tutorial] could not mount progress thread:', e));
  } else if (backLink) {
    backLink.addEventListener("click", function (event) {
      event.preventDefault();
      window.location.href = '/mode-select.html';
    });
  }
  createButtons();
});
