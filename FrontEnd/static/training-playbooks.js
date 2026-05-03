/**
 * Custom Training Playbook — select offense/defense rows for CMD training distribution.
 * Persists selection to sessionStorage; Training Orders submit sends training_playbook_focus.
 */
(function () {
  const STORAGE_FOCUS = 'gob_training_playbook_focus';
  const STORAGE_MODE = 'gob_playbook_training_mode';
  const STORAGE_INSTALL = 'gob_training_team_drills_snapshot';

  const params = new URLSearchParams(window.location.search);
  const mode = params.get('mode') || 'franchise';
  const franchiseId = params.get('franchise_id') || '';
  const teamId = params.get('team_id') || params.get('user_team_id') || '';

  const offenseSel = new Set();
  const defenseSel = new Set();
  let totalOffenseCards = 0;
  let totalDefenseCards = 0;

  function readInstallSnapshot() {
    try {
      const raw = sessionStorage.getItem(STORAGE_INSTALL);
      if (!raw) return { offense: 0, defense: 0 };
      const o = JSON.parse(raw);
      return {
        offense: Number(o?.team_offense?.install ?? 0) || 0,
        defense: Number(o?.team_defense?.install ?? 0) || 0,
      };
    } catch (e) {
      return { offense: 0, defense: 0 };
    }
  }

  function motionFocusLabel(v) {
    if (v === 'inside') return 'Inside';
    if (v === 'attack') return 'Attack';
    if (v === 'outside') return 'Outside';
    return 'Balanced';
  }

  function cmdBarClass(n) {
    if (n < 41) return 'is-red';
    if (n <= 60) return 'is-yellow';
    if (n <= 80) return 'is-green';
    return 'is-blue';
  }

  function trainingOrdersUrl() {
    const q = new URLSearchParams();
    if (franchiseId) q.set('franchise_id', franchiseId);
    if (teamId) q.set('team_id', teamId);
    q.set('mode', mode);
    q.set('from', 'locker-room');
    q.set('session_type', params.get('session_type') || 'in-season');
    return `/training.html?${q.toString()}`;
  }

  function showToast(title, subtitle) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.innerHTML = `
      <div class="toast-icon" aria-hidden="true"></div>
      <div class="toast-copy">
        <div class="toast-title">${title}</div>
        ${subtitle ? `<div class="toast-subline">${subtitle}</div>` : ''}
      </div>
      <button type="button" class="toast-dismiss" aria-label="Dismiss">×</button>
    `;
    toast.hidden = false;
    requestAnimationFrame(() => toast.classList.add('visible'));
    const dismiss = () => {
      toast.classList.remove('visible');
      setTimeout(() => {
        toast.hidden = true;
      }, 220);
    };
    toast.querySelector('.toast-dismiss')?.addEventListener('click', dismiss, { once: true });
    setTimeout(dismiss, 3200);
  }

  function pccIndex1Based(pcList, id) {
    const idx = (pcList || []).findIndex((x) => String(x) === String(id));
    return idx >= 0 ? idx + 1 : null;
  }

  function buildOffenseCards(data) {
    const pctRoot =
      data.simple_playbook_percentages ||
      data.playbook_percentages ||
      {};
    const motionPct = pctRoot.motion || {};
    const setPct = pctRoot.set_plays || {};
    const pcOff = (data.pc_order && data.pc_order.offense) || [];
    const motionDd = data.motion_dropdowns || {};

    const motion = (data.motion || []).map((play) => {
      const pid = String(play.play_id);
      const mf = play.motion_focus != null ? play.motion_focus : motionDd[pid];
      return {
        kind: 'offense',
        id: pid,
        name: play.name,
        isMotion: true,
        pct: Number(motionPct[pid] ?? motionPct[play.play_id] ?? 0) || 0,
        cmd: Number(play.effectiveness ?? 0) || 0,
        metaLine: `Focus · ${motionFocusLabel(mf)}`,
        pcc: pccIndex1Based(pcOff, pid),
      };
    });

    const sets = (data.set_plays || []).map((play) => {
      const pid = String(play.play_id);
      const tgt = play.target_shooter || 'PG';
      return {
        kind: 'offense',
        id: pid,
        name: play.name,
        isMotion: false,
        pct: Number(setPct[pid] ?? 0) || 0,
        cmd: Number(play.effectiveness ?? 0) || 0,
        metaLine: `Target · ${tgt}`,
        pcc: pccIndex1Based(pcOff, pid),
      };
    });

    const rows = motion.concat(sets);
    rows.sort((a, b) => {
      if (b.pct !== a.pct) return b.pct - a.pct;
      return b.cmd - a.cmd;
    });
    return rows;
  }

  function buildDefenseCards(data) {
    const pctRoot =
      data.simple_playbook_percentages ||
      data.playbook_percentages ||
      {};
    const manPct = pctRoot.man_defense || {};
    const zonePct = pctRoot.zone_defense || {};
    const pcDef = (data.pc_order && data.pc_order.defense) || [];

    const man = (data.man_defense_rows || []).map((row) => {
      const id = String(row.id);
      return {
        kind: 'defense',
        id,
        name: row.name,
        pct: Number(manPct[id] ?? 0) || 0,
        cmd: Number(row.effectiveness ?? 0) || 0,
        metaLine: '',
        pcc: pccIndex1Based(pcDef, id),
      };
    });

    const zone = (data.zone_defense_rows || []).map((row) => {
      const id = String(row.id);
      return {
        kind: 'defense',
        id,
        name: row.name,
        pct: Number(zonePct[id] ?? 0) || 0,
        cmd: Number(row.effectiveness ?? 0) || 0,
        metaLine: '',
        pcc: pccIndex1Based(pcDef, id),
      };
    });

    const rows = man.concat(zone);
    rows.sort((a, b) => {
      if (b.pct !== a.pct) return b.pct - a.pct;
      return b.cmd - a.cmd;
    });
    return rows;
  }

  function renderCard(container, row, selectedSet) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tp-card' + (selectedSet.has(row.id) ? ' is-selected' : '');
    btn.dataset.id = row.id;
    btn.setAttribute('aria-pressed', selectedSet.has(row.id) ? 'true' : 'false');

    const top = document.createElement('div');
    top.className = 'tp-card-top';
    const name = document.createElement('div');
    name.className = 'tp-card-name';
    name.textContent = row.name;
    const pct = document.createElement('div');
    pct.className = 'tp-card-pct';
    pct.textContent = `${row.pct}% PB`;
    top.appendChild(name);
    top.appendChild(pct);

    const meta = document.createElement('div');
    meta.className = 'tp-card-meta';
    if (row.metaLine) {
      const chip = document.createElement('span');
      chip.className = 'tp-chip';
      chip.textContent = row.metaLine;
      meta.appendChild(chip);
    }
    if (row.pcc != null) {
      const pcc = document.createElement('span');
      pcc.className = 'tp-chip tp-chip-pcc';
      pcc.textContent = `PCC · ${row.pcc}`;
      meta.appendChild(pcc);
    }

    const cmdRow = document.createElement('div');
    cmdRow.className = 'tp-cmd-row';
    const lab = document.createElement('span');
    lab.className = 'tp-cmd-label';
    lab.textContent = 'CMD';
    const track = document.createElement('div');
    track.className = 'tp-cmd-track';
    const fill = document.createElement('div');
    fill.className = 'tp-cmd-fill ' + cmdBarClass(row.cmd);
    fill.style.width = `${Math.min(100, row.cmd)}%`;
    track.appendChild(fill);
    const num = document.createElement('span');
    num.className = 'tp-cmd-num';
    num.textContent = String(row.cmd);
    const chk = document.createElement('span');
    chk.className = 'tp-check';
    chk.setAttribute('aria-hidden', 'true');
    cmdRow.appendChild(chk);
    cmdRow.appendChild(lab);
    cmdRow.appendChild(track);
    cmdRow.appendChild(num);

    btn.appendChild(top);
    if (meta.childElementCount) btn.appendChild(meta);
    btn.appendChild(cmdRow);

    btn.addEventListener('click', () => {
      if (selectedSet.has(row.id)) selectedSet.delete(row.id);
      else selectedSet.add(row.id);
      syncCardVisual(btn, row.id, selectedSet);
      updateDock();
      updateSaveState();
    });

    container.appendChild(btn);
  }

  function syncCardVisual(btn, id, set) {
    const on = set.has(id);
    btn.classList.toggle('is-selected', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  function updateDock() {
    const inst = readInstallSnapshot();
    const no = offenseSel.size;
    const nd = defenseSel.size;
    const offPct = no === 0 ? '—' : `${Math.round(100 / no)}%`;
    const defPct = nd === 0 ? '—' : `${Math.round(100 / nd)}%`;
    document.getElementById('tp-dock-off-pct').textContent = offPct;
    document.getElementById('tp-dock-def-pct').textContent = defPct;
    const offTot = Math.max(1, totalOffenseCards);
    const defTot = Math.max(1, totalDefenseCards);
    document.getElementById('tp-dock-off-fill').style.width = `${no === 0 ? 0 : (no / offTot) * 100}%`;
    document.getElementById('tp-dock-def-fill').style.width = `${nd === 0 ? 0 : (nd / defTot) * 100}%`;

    const offMeta = document.getElementById('tp-dock-off-meta');
    const defMeta = document.getElementById('tp-dock-def-meta');
    offMeta.innerHTML =
      no === 0
        ? '<span class="tp-warn">At least 1 required</span>'
        : `<span>${no} of ${totalOffenseCards} included</span>`;
    defMeta.innerHTML =
      nd === 0
        ? '<span class="tp-warn">At least 1 required</span>'
        : `<span>${nd} of ${totalDefenseCards} included</span>`;

    document.getElementById('tp-dock-off-install').textContent =
      `Offense Install · ${inst.offense} PTS`;
    document.getElementById('tp-dock-def-install').textContent =
      `Defense Install · ${inst.defense} PTS`;
  }

  function updateSaveState() {
    const ok = offenseSel.size >= 1 && defenseSel.size >= 1;
    document.getElementById('tp-save').disabled = !ok;
    document.getElementById('tp-save-footer').disabled = !ok;
  }

  function loadPriorSelection() {
    try {
      const raw = sessionStorage.getItem(STORAGE_FOCUS);
      if (!raw) return;
      const o = JSON.parse(raw);
      (o.offense || []).forEach((id) => offenseSel.add(String(id)));
      (o.defense || []).forEach((id) => defenseSel.add(String(id)));
    } catch (e) {}
  }

  function persistAndLeave() {
    const payload = {
      offense: Array.from(offenseSel),
      defense: Array.from(defenseSel),
    };
    sessionStorage.setItem(STORAGE_FOCUS, JSON.stringify(payload));
    sessionStorage.setItem(STORAGE_MODE, 'custom');
    showToast('Playbooks Saved', 'Custom training playbook updated.');
    setTimeout(() => {
      window.location.href = trainingOrdersUrl();
    }, 400);
  }

  function wireNav() {
    document.getElementById('tp-back').addEventListener('click', (e) => {
      e.preventDefault();
      window.location.href = trainingOrdersUrl();
    });
    document.getElementById('tp-cancel').addEventListener('click', () => {
      window.location.href = trainingOrdersUrl();
    });
    document.getElementById('tp-save').addEventListener('click', persistAndLeave);
    document.getElementById('tp-save-footer').addEventListener('click', persistAndLeave);
  }

  async function init() {
    if (!franchiseId || !teamId) {
      alert('Missing franchise or team. Open this page from Training Orders.');
      window.location.href = '/mode-select.html';
      return;
    }
    wireNav();
    loadPriorSelection();

    const url = new URL(
      typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl
        ? API_CONFIG.buildUrl('/api/playbooks')
        : '/api/playbooks',
      window.location.origin
    );
    url.searchParams.set('mode', mode);
    url.searchParams.set('team_id', teamId);
    url.searchParams.set('franchise_id', franchiseId);

    const res = await fetch(url.toString());
    if (!res.ok) {
      alert('Failed to load playbooks.');
      return;
    }
    const data = await res.json();

    const offGrid = document.getElementById('tp-offense-grid');
    const defGrid = document.getElementById('tp-defense-grid');
    offGrid.innerHTML = '';
    defGrid.innerHTML = '';

    const offenseRows = buildOffenseCards(data);
    const defenseRows = buildDefenseCards(data);
    totalOffenseCards = offenseRows.length;
    totalDefenseCards = defenseRows.length;
    offenseRows.forEach((row) => renderCard(offGrid, row, offenseSel));
    defenseRows.forEach((row) => renderCard(defGrid, row, defenseSel));

    offGrid.querySelectorAll('.tp-card').forEach((btn) => {
      syncCardVisual(btn, btn.dataset.id, offenseSel);
    });
    defGrid.querySelectorAll('.tp-card').forEach((btn) => {
      syncCardVisual(btn, btn.dataset.id, defenseSel);
    });

    updateDock();
    updateSaveState();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
