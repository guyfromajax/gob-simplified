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

function createButtons() {
  const container = document.getElementById("team-container");
  teams.forEach(team => {
    const btn = document.createElement("button");
    btn.className = "team-button";
    btn.innerHTML = `<img src="${typeof getTeamAssetPath === 'function' ? getTeamAssetPath(team, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg'}" alt="${team}"><span>${taglines[team] || team}</span>`;
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
        if (res.status === 400 && typeof msg === 'string' && msg.includes('already have an active franchise')) {
          alert(msg + "\n\nGo to the main menu and click \"New Franchise\" to delete your current one and start fresh.");
          window.location.href = '/mode-select.html';
          return;
        }
      } catch (_) {}
      throw new Error(msg);
    }
    const data = await res.json();
    localStorage.setItem("franchiseId", data.franchise_id);
    localStorage.setItem("franchise_user_team", team);
    window.location.href = `./franchise-command-center.html?franchise_id=${encodeURIComponent(data.franchise_id)}`;
  } catch (err) {
    console.error(err);
    alert(err.message || "Unable to start franchise");
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
  createButtons();
});
