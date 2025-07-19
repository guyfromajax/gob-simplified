async function fetchJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Request failed');
    return await res.json();
  } catch (err) {
    console.error('Failed loading', url, err);
    return null;
  }
}

const teamMap = {
  "Four Corners": "FC",
  "Bentley-Truman": "BT",
  "Lancaster": "Lan",
  "Little York": "LY",
  "Morristown": "Mor",
  "Ocean City": "OC",
  "South Lancaster": "SL",
  "Xavien": "Xav",
};

const teamIdNameMap = {};

function populateTop(data) {
  if (!data) return;
  document.querySelector('.username').textContent = data.username || 'User';
  document.querySelector('.seed').textContent = `Seed: ${data.seed || '--'}`;
  document.getElementById('team-logo').src = `/static/images/homepage-logos/${data.team}.png`;

  const abbr = teamMap[data.team];
  const sammyEl = document.getElementById('coach-sammy');
  const maryEl = document.getElementById('coach-mary');
  if (abbr) {
    if (sammyEl) sammyEl.src = `/static/images/coaches/${abbr}/Sammy-${abbr}.png`;
    if (maryEl) maryEl.src = `/static/images/coaches/${abbr}/Mary-${abbr}.png`;
  } else {
    if (sammyEl) sammyEl.removeAttribute('src');
    if (maryEl) maryEl.removeAttribute('src');
  }

  document.querySelector('.chemistry-bar').textContent = `${data.team_chemistry || 0} / 25`;
  document.getElementById('stat-offense').textContent = `Offense: ${data.offense || '--'}`;
  document.getElementById('stat-defense').textContent = `Defense: ${data.defense || '--'}`;
  document.getElementById('stat-athleticism').textContent = `Athleticism: ${data.athleticism || '--'}`;
  document.getElementById('stat-intangibles').textContent = `Intangibles: ${data.intangibles || '--'}`;
  document.getElementById('stat-prestige').textContent = `Prestige: ${data.prestige || '--'}`;
  document.getElementById('stat-rank').textContent = `Nat'l Rank: ${data.rank || '--'}`;
}

function renderStandings(data) {
  if (!data) return;
  const tbody = document.getElementById('standings-body');
  tbody.innerHTML = '';
  (data.standings || []).forEach(t => {
    teamIdNameMap[t.team_id] = t.name;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${t.name}</td><td>${t.W}</td><td>${t.L}</td><td>${t.pct.toFixed(3)}</td><td>${t.PF}</td><td>${t.PA}</td><td>${t.next}</td>`;
    tbody.appendChild(tr);
  });
}

function renderLeaders(data) {
  if (!data) return;
  const container = document.getElementById('leaders-container');
  container.innerHTML = '';
  const categories = Object.keys(data);
  categories.forEach(cat => {
    const section = document.createElement('div');
    const h3 = document.createElement('h3');
    h3.textContent = cat;
    section.appendChild(h3);
    const div = document.createElement('div');
    div.className = 'scroll-x';
    const table = document.createElement('table');
    table.className = 'leaders-table';
    table.innerHTML = '<thead><tr><th>Rank</th><th>Player</th><th>Team</th><th>Value</th></tr></thead>';
    const body = document.createElement('tbody');
    (data[cat] || []).forEach((p, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${idx + 1}</td><td>${p.name}</td><td>${p.team}</td><td>${p.value}</td>`;
      body.appendChild(tr);
    });
    table.appendChild(body);
    div.appendChild(table);
    section.appendChild(div);
    container.appendChild(section);
  });
}

function renderTeamStats(data) {
  if (!data) return;
  const tbody = document.getElementById('teamstats-body');
  tbody.innerHTML = '';
  data.teams.forEach(t => {
    const tr = document.createElement('tr');
    const s = t.stats || {};
    tr.innerHTML = `<td>${t.team}</td><td>${s.PTS || 0}</td><td>${s.REB || 0}</td><td>${s.AST || 0}</td><td>${s.STL || 0}</td><td>${s.BLK || 0}</td>`;
    tbody.appendChild(tr);
  });
}

function renderRecruits(data) {
  if (!data) return;
  const tbody = document.getElementById('recruits-body');
  tbody.innerHTML = '';
  data.recruits.forEach(r => {
    const tr = document.createElement('tr');
    const a = r.attributes || {};
    tr.innerHTML = `<td>${r.name}</td><td>${a.SC}</td><td>${a.SH}</td><td>${a.ID}</td><td>${a.OD}</td><td>${a.PS}</td><td>${a.BH}</td><td>${a.RB}</td><td>${a.AG}</td><td>${a.ST}</td><td>${a.ND}</td><td>${a.IQ}</td><td>${a.FT}</td>`;
    tbody.appendChild(tr);
  });
}

function renderTeam(data) {
  if (!data) return;
  const tbody = document.getElementById('team-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  const headers = ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT","NG"];
  (data.players || []).forEach(p => {
    const tr = document.createElement('tr');
    let html = `<td>${p.name}</td>`;
    headers.forEach(h => {
      let val = p.attributes ? p.attributes[h] : null;
      if (h === 'NG') val = (val ?? 0).toFixed(2);
      else val = Math.round(val ?? 0);
      html += `<td>${val}</td>`;
    });
    tr.innerHTML = html;
    tbody.appendChild(tr);
  });
}

function renderSchedule(data) {
  if (!data) return;
  const container = document.getElementById('schedule-container');
  if (!container) return;
  container.innerHTML = '';
  (data.schedule || []).forEach((weekGames, idx) => {
    const weekDiv = document.createElement('div');
    weekDiv.className = 'schedule-week';
    const h4 = document.createElement('h4');
    h4.textContent = `Week ${idx + 1}`;
    weekDiv.appendChild(h4);
    weekGames.forEach(g => {
      const gameDiv = document.createElement('div');
      gameDiv.className = 'schedule-game';
      const away = teamIdNameMap[g.away_team_id] || g.away_team_id;
      const home = teamIdNameMap[g.home_team_id] || g.home_team_id;
      let text = '';
      if (g.status === 'complete') {
        let awayStr = `${away} (${g.away_score})`;
        let homeStr = `${home} (${g.home_score})`;
        if (g.away_score > g.home_score) awayStr = `<strong>${awayStr}</strong>`;
        if (g.home_score > g.away_score) homeStr = `<strong>${homeStr}</strong>`;
        text = `${awayStr} at ${homeStr}`;
      } else {
        text = `${away} at ${home}`;
      }
      gameDiv.innerHTML = text;
      weekDiv.appendChild(gameDiv);
    });
    container.appendChild(weekDiv);
  });
}

async function init() {
  const topData = await fetchJSON('/franchise/command-center/data');
  populateTop(topData);
  if (topData && topData.team) {
    renderTeam(await fetchJSON(`/roster/${encodeURIComponent(topData.team)}`));
  }
  renderStandings(await fetchJSON('/franchise/standings'));
  renderSchedule(await fetchJSON('/franchise/schedule'));
  renderLeaders(await fetchJSON('/franchise/leaders'));
  renderTeamStats(await fetchJSON('/franchise/team-stats'));
  renderRecruits(await fetchJSON('/franchise/recruits'));
}

document.getElementById('play-now').addEventListener('click', async () => {
  await fetch('/franchise/play-next-game', { method: 'POST' });
  window.location.href = '/animation';
});

window.addEventListener('DOMContentLoaded', init);
