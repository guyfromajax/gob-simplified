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

let franchiseId = null;
const ATTR_HEADERS = ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT"];

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
  const formattedTeam = formatTeamName(data.team);
  const logoSrc = `/static/images/homepage-logos/${formattedTeam}.png`;
  document.getElementById('team-logo').src = logoSrc;
  console.log('Team logo URL:', logoSrc);

  const abbr = teamMap[formattedTeam];
  const sammyEl = document.getElementById('coach-sammy');
  const dukeEl = document.getElementById('coach-duke');
  if (abbr) {
    if (sammyEl) {
      sammyEl.src = `/static/images/coaches/${abbr}/Sammy-${abbr}.png`;
      console.log('Coach Sammy URL:', sammyEl.src);
    }
    if (dukeEl) {
      dukeEl.src = `/static/images/coaches/${abbr}/Duke-${abbr}.png`;
      console.log('Coach Duke URL:', dukeEl.src);
    }
  } else {
    if (sammyEl) sammyEl.removeAttribute('src');
    if (dukeEl) dukeEl.removeAttribute('src');
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
  let players = (data.players || []).map(p => {
    const best = getBestPosition(p.position_ratings || {});
    return {
      name: p.name,
      pos: best.pos,
      year: yearMap[p.year?.toLowerCase()] || p.year || '--',
      height: formatHeight(p.height),
      weight: p.weight ?? '--',
      attributes: p.attributes || {},
      rt: best.rating,
    };
  });
  players.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  players.forEach(p => {
    const tr = document.createElement('tr');
    let html = `<td>${p.name}</td><td>${p.pos}</td><td>${p.year}</td><td>${p.height}</td><td>${p.weight}</td>`;
    ATTR_HEADERS.forEach(h => {
      const val = p.attributes ? p.attributes[h] : undefined;
      html += `<td>${val ?? '--'}</td>`;
    });
    html += `<td>${p.rt ?? '-'}</td>`;
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
  const standingsData = await fetchJSON(`/franchise/standings?franchise_id=${franchiseId}`);
  console.log("standings keys", Object.keys(standingsData || {}));
  renderStandings(standingsData);
  const scheduleData = await fetchJSON(`/franchise/schedule?franchise_id=${franchiseId}`);
  console.log("schedule keys", Object.keys(scheduleData || {}));
  renderSchedule(scheduleData);
  renderLeaders(await fetchJSON('/franchise/leaders'));
  renderTeamStats(await fetchJSON('/franchise/team-stats'));
  renderRecruits(await fetchJSON('/franchise/recruits'));
}

const playNowBtn = document.getElementById('play-now');
playNowBtn.disabled = true;
playNowBtn.addEventListener('click', async () => {
  console.log('Play Now click search:', window.location.search);
  const originalText = playNowBtn.textContent;
  playNowBtn.disabled = true;
  playNowBtn.textContent = 'Loading...';
  if (!franchiseId) {
    alert('Franchise not loaded');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
    return;
  }
  try {
    const res = await fetch('/franchise/play-next-game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: franchiseId })
    });
    if (!res.ok) throw new Error('Simulation failed');
    const { home, away, week } = await res.json();
    if (!home || !away) throw new Error('Matchup not found');
    try {
      localStorage.setItem('franchise_week', week);
    } catch {}
    const url = `/court.html?franchise_id=${encodeURIComponent(franchiseId)}&week=${week}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`;
    console.log('Navigating to', url);
    window.location.href = url;
  } catch (err) {
    console.error(err);
    alert('Unable to play next game');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
  }
});

window.addEventListener('DOMContentLoaded', () => {
  franchiseId = localStorage.getItem('franchiseId');
  if (franchiseId) {
    playNowBtn.disabled = false;
  }
  init();
});
