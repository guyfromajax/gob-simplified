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

function populateTop(data) {
  if (!data) return;
  document.querySelector('.username').textContent = data.username || 'User';
  document.querySelector('.seed').textContent = `Seed: ${data.seed || '--'}`;
  document.getElementById('team-logo').src = `/static/images/homepage-logos/${data.team}.png`;
  document.getElementById('coach-sammy').src = '/static/images/coach.png';
  document.getElementById('coach-mary').src = '/static/images/fan.png';
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
  data.standings.forEach((t, i) => {
    const tr = document.createElement('tr');
    const rec = t.record || {W:0,L:0};
    tr.innerHTML = `<td>${i + 1}</td><td>${t.name}</td><td>${rec.W}-${rec.L}</td>`;
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

async function init() {
  populateTop(await fetchJSON('/franchise/command-center/data'));
  renderStandings(await fetchJSON('/franchise/standings'));
  renderLeaders(await fetchJSON('/franchise/leaders'));
  renderTeamStats(await fetchJSON('/franchise/team-stats'));
  renderRecruits(await fetchJSON('/franchise/recruits'));
}

document.getElementById('play-now').addEventListener('click', async () => {
  await fetch('/franchise/play-next-game', { method: 'POST' });
  window.location.href = '/animation';
});

window.addEventListener('DOMContentLoaded', init);
