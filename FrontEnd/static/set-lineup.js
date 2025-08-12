const urlParams = new URLSearchParams(window.location.search);
const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');
const myTeamSide = urlParams.get('my_team') || 'home';
const teamName = myTeamSide === 'away' ? awayTeam : homeTeam;

let roster = [];
const lineup = {};
const playerMap = {};

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2000);
}

async function loadRoster() {
  if (!teamName) return;
  const res = await fetch(`/roster/${encodeURIComponent(teamName)}`);
  if (!res.ok) return;
  const data = await res.json();
  roster = data.players || [];
  roster.forEach(p => playerMap[p._id] = p);
  renderRoster();
}

function renderRoster() {
  const tbody = document.getElementById('roster-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  roster.forEach(p => {
    const tr = document.createElement('tr');
    tr.draggable = true;
    tr.dataset.playerId = p._id;
    tr.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', p._id);
    });

    const rt = Math.max(...Object.values(p.position_ratings || {}));
    const cells = [
      p.name,
      formatHeight(p.height),
      p.weight ?? '--',
      p.attributes.SC, p.attributes.SH, p.attributes.ID, p.attributes.OD,
      p.attributes.PS, p.attributes.BH, p.attributes.RB, p.attributes.ST,
      p.attributes.AG, p.attributes.ND, p.attributes.IQ, p.attributes.FT,
      p.attributes.NG, rt
    ];
    const classes = ['','ht','wt','','','','','','','','','','','','','', 'rt'];
    cells.forEach((val, idx) => {
      const td = document.createElement('td');
      td.textContent = val ?? '--';
      if (classes[idx]) td.classList.add(classes[idx]);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function updatePlayButton() {
  const btn = document.getElementById('play-now');
  if (!btn) return;
  const filled = ['PG','SG','SF','PF','C'].every(pos => lineup[pos]);
  if (filled) {
    btn.classList.remove('disabled');
  } else {
    btn.classList.add('disabled');
  }
}

function clearSlot(slot) {
  const pos = slot.dataset.pos;
  delete lineup[pos];
  slot.textContent = pos;
  const remove = document.createElement('button');
  remove.className = 'remove';
  remove.textContent = '✕';
  remove.hidden = true;
  slot.appendChild(remove);
  slot.classList.remove('filled');
  remove.addEventListener('click', () => clearSlot(slot));
  updatePlayButton();
}

function setupSlots() {
  document.querySelectorAll('.slot').forEach(slot => {
    clearSlot(slot);
    slot.addEventListener('dragover', e => e.preventDefault());
    slot.addEventListener('drop', e => {
      e.preventDefault();
      const playerId = e.dataTransfer.getData('text/plain');
      const pos = slot.dataset.pos;
      if (lineup[pos]) {
        showToast('Slot already filled');
        return;
      }
      if (Object.values(lineup).includes(playerId)) {
        showToast('Player already used');
        return;
      }
      const player = playerMap[playerId];
      if (!player) return;
      const rating = player.position_ratings?.[pos] ?? '--';
      slot.textContent = `${player.name} — ${rating}`;
      const remove = document.createElement('button');
      remove.className = 'remove';
      remove.textContent = '✕';
      remove.addEventListener('click', () => clearSlot(slot));
      slot.appendChild(remove);
      slot.classList.add('filled');
      lineup[pos] = playerId;
      updatePlayButton();
    });
  });
}

async function init() {
  await loadRoster();
  setupSlots();
  const btn = document.getElementById('play-now');
  if (btn) {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('disabled')) return;
      const params = new URLSearchParams(window.location.search);
      ['PG','SG','SF','PF','C'].forEach(pos => {
        const id = lineup[pos];
        if (id) params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
      });
      window.location.href = `/court.html?${params.toString()}`;
    });
  }
}

document.addEventListener('DOMContentLoaded', init);
