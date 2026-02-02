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
    btn.innerHTML = `<img src="./images/homepage-logos/${team}.png" alt="${team} logo"><span>${team}</span>`;
    btn.addEventListener("click", () => selectTeam(team));
    container.appendChild(btn);
  });
}

async function selectTeam(team) {
  try {
    const headers = { ...API_CONFIG.getAuthHeaders(), "Content-Type": "application/json" };
    const res = await fetch(API_CONFIG.buildUrl('/tournament/start'), {
      method: "POST",
      headers,
      body: JSON.stringify({ user_team_id: team })
    });
    if (!res.ok) {
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

document.addEventListener("DOMContentLoaded", createButtons);
