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

function createButtons() {
  const container = document.getElementById("team-container");
  teams.forEach(team => {
    const btn = document.createElement("button");
    btn.className = "team-button";
    btn.innerHTML = `<img src="${typeof getTeamAssetPath === 'function' ? getTeamAssetPath(team, 'logo_square') : './images/homepage-logos/' + team + '.png'}" alt="${team} logo"><span>${team}</span>`;
    btn.addEventListener("click", () => {
      playSound("click-beep.wav");
      selectTeam(team);
    });
    container.appendChild(btn);
  });
}

async function selectTeam(team) {
  try {
    const headers = { ...API_CONFIG.getAuthHeaders(), "Content-Type": "application/json" };
    const res = await fetch(API_CONFIG.buildUrl('/tournament/start?profile=1'), {
      method: "POST",
      headers,
      body: JSON.stringify({ user_team_id: team })
    });
    if (!res.ok) {
      if (res.status === 401) {
        // Token invalid/expired - clear and redirect to login
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        window.location.href = '/login.html?redirect=' + encodeURIComponent(window.location.pathname);
        return;
      }
      let msg = "Unable to start tournament";
      try {
        const errBody = await res.json();
        if (errBody.detail) msg = errBody.detail;
      } catch (_) {}
      throw new Error(msg);
    }
    const tournament = await res.json();
    localStorage.setItem("activeTournament", JSON.stringify(tournament));
    localStorage.setItem("userTeamId", team);
    window.location.href = "./tournament.html";
  } catch (err) {
    console.error(err);
    alert(err.message || "Unable to start tournament");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  // Looping lobby music on tournament team-select screen
  try {
    var lobbyMusic = new Audio("/sounds/crossover-21738.mp3");
    lobbyMusic.loop = true;
    lobbyMusic.volume = 0.4;
    lobbyMusic.play().catch(function () {});
  } catch (e) {}
  createButtons();
});
