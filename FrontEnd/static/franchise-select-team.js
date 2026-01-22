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
    btn.innerHTML = `<img src="/images/homepage-logos/${team}.png" alt="${team} logo"><span>${team}</span>`;
    btn.addEventListener("click", () => selectTeam(team));
    container.appendChild(btn);
  });
}

async function selectTeam(team) {
  try {
    // Use centralized API config for consistent backend URL
    const res = await fetch(API_CONFIG.buildUrl('/franchise/select-team'), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: team })
    });
    if (!res.ok) throw new Error("Failed to start franchise");
    const data = await res.json();
    localStorage.setItem("franchiseId", data.franchise_id);
    localStorage.setItem("franchise_user_team", team);
    window.location.href = `./franchise-command-center.html?franchise_id=${encodeURIComponent(data.franchise_id)}`;
  } catch (err) {
    console.error(err);
    alert("Unable to start franchise");
  }
}

document.addEventListener("DOMContentLoaded", createButtons);
