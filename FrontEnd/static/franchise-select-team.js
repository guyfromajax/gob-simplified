function playSound(filename) {
  try {
    var a = new Audio("/sounds/" + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function () {});
  } catch (e) {}
}

const errorHost = document.getElementById("team-select-error");
const loadingOverlay = document.getElementById("team-select-loading");
const loadingBanner = document.getElementById("team-select-loading-banner");
const loadingSubline = document.getElementById("team-select-loading-subline");
const backLink = document.getElementById("team-select-back-link");
const pickerRoot = document.getElementById("team-container");

// FTE v2 tutorial branch: when ?mode=tutorial is present, this page is the
// first step of the new-user funnel rather than a franchise-creation entry.
const TUTORIAL_MODE = new URLSearchParams(window.location.search).get("mode") === "tutorial";
const HOME_SLOT_PARAM = (function () {
  const n = parseInt(new URLSearchParams(window.location.search).get("home_slot"), 10);
  return n === 1 || n === 2 ? n : null;
})();

let teamPicker = null;

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

function scoutTeam(team) {
  const name = team && team.name ? team.name : team;
  playSound("click-beep.wav");
  const scoutParams = new URLSearchParams();
  scoutParams.set('team_name', name);
  scoutParams.set('return_url', buildReturnUrl());
  // FTE v2 tutorial: carry mode=tutorial so authBarInit's routeToTutorial
  // treats team-roster-view as a shoulder page and doesn't bounce the
  // user back to the team-select step.
  if (TUTORIAL_MODE) scoutParams.set('mode', 'tutorial');
  window.location.href = '/team-roster-view.html?' + scoutParams.toString();
}

// FTE v2 tutorial flow: team selection records the pick in tutorial_state,
// opens the username modal with team-aware copy, and on submit routes to the
// situation card page. No franchise is created here — the tutorial game is
// throwaway (single mode behind the scenes).
async function selectTutorialTeam(team) {
  const name = team && team.name ? team.name : team;
  hideError();
  if (teamPicker) teamPicker.setSelected(team);
  try {
    // Step 1: persist the team pick + advance tutorial_state to "username".
    const advanceRes = await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'username', team_pick: name }),
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
  // Pre-fill the input with the user's existing username (if any) so
  // returning users who are being re-funnel'd through the funnel (post-
  // reset_fte_v2_for_all) can confirm-without-retyping. New signups
  // get an empty input as before.
  const mascot = (team && team.mascot) || name;
  let existingUsername = '';
  try {
    const raw = localStorage.getItem('auth_user');
    if (raw) existingUsername = (JSON.parse(raw) || {}).username || '';
  } catch (_) { /* private mode / corrupt JSON — fall back to empty */ }
  const { openUsernameModal } = await import('/js/shared/usernameModal.js');
  openUsernameModal({
    teamName: name,
    mascot,
    initialUsername: existingUsername,
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
  const name = team && team.name ? team.name : team;
  hideError();
  showLoading(name);
  try {
    const headers = { ...API_CONFIG.getAuthHeaders(), "Content-Type": "application/json" };
    const payload = { team_name: name };
    if (HOME_SLOT_PARAM) payload.home_slot = HOME_SLOT_PARAM;
    const res = await fetch(API_CONFIG.buildUrl('/franchise/select-team?profile=1'), {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
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
    if (window.FranchiseLS && data.franchise_id) {
      window.FranchiseLS.clearBareKeys();
      window.FranchiseLS.setTeamContext(data.franchise_id, { teamName: name });
    }
    window.location.href = `./franchise-command-center.html?franchise_id=${encodeURIComponent(data.franchise_id)}`;
  } catch (err) {
    console.error(err);
    hideLoading();
    showError(err.message || "Unable to start franchise");
  }
}

function mountTeamPicker() {
  if (!pickerRoot || !window.TeamPicker) {
    showError('Team picker failed to load. Refresh and try again.');
    return;
  }

  teamPicker = window.TeamPicker.mount(pickerRoot, {
    primaryAction: {
      label: 'Select',
      onClick: function (team) {
        if (TUTORIAL_MODE) {
          selectTutorialTeam(team);
        } else {
          selectTeam(team);
        }
      },
    },
    secondaryAction: {
      label: 'Scout',
      onClick: scoutTeam,
    },
    // Task B Step 0 will enable confirmation + swap CTA; franchise select
    // keeps the existing immediate-create path.
    confirmation: { enabled: false },
  });
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
    const tbEntry = document.getElementById('team-builder-entry');
    if (tbEntry) tbEntry.hidden = true;
    // Mount the quiet 5-step progress thread (Pick Program = step 2 of 5).
    import('/js/shared/tutorialProgressThread.js')
      .then(({ mountTutorialProgress }) => mountTutorialProgress('program'))
      .catch((e) => console.warn('[tutorial] could not mount progress thread:', e));
  } else if (backLink) {
    backLink.addEventListener("click", function (event) {
      event.preventDefault();
      window.location.href = '/mode-select.html';
    });
    const tbCta = document.getElementById('team-builder-cta');
    if (tbCta && HOME_SLOT_PARAM) {
      tbCta.href = '/team-builder.html?home_slot=' + HOME_SLOT_PARAM;
    }
  }
  mountTeamPicker();
});
