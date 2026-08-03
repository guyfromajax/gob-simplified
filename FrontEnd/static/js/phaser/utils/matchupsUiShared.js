/**
 * Shared DNA for franchise pre-game experience + in-game defense matchups modal.
 */

export const POSITIONS = Object.freeze(["PG", "SG", "SF", "PF", "C"]);

export const POSITION_COLORS = Object.freeze({
  PG: "#4A90D9",
  SG: "#7B5EA7",
  SF: "#3A8C4A",
  PF: "#C0392B",
  C: "#D4A017",
});

/** RT color from the shared grade presentation. */
export function rtBadgeBg(rt) {
  return typeof window !== "undefined" && typeof window.getRtColor === "function"
    ? window.getRtColor(rt)
    : "#c8ccd6";
}

export function formatRtDisplay(rt) {
  if (typeof window !== "undefined" && typeof window.formatRtDisplay === "function") {
    return window.formatRtDisplay(rt);
  }
  return "--";
}

export function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(String(hex || ""));
  return result
    ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
    : "255, 255, 255";
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function playerImageUrl(playerId) {
  if (
    playerId &&
    typeof window !== "undefined" &&
    window.API_CONFIG &&
    typeof window.API_CONFIG.getPlayerImageUrl === "function"
  ) {
    return window.API_CONFIG.getPlayerImageUrl(playerId, { size: "card" });
  }
  return playerId ? `/images/players/${playerId}.png` : "";
}

const SILHOUETTE = `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="34" r="19" fill="rgba(255,255,255,0.16)"/><path d="M12 100c0-22 17-36 38-36s38 14 38 36" fill="rgba(255,255,255,0.16)"/></svg>`;

const DRAG_HINT = `<span class="dm-draghint" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="9" cy="6" r="1.4"/><circle cx="15" cy="6" r="1.4"/><circle cx="9" cy="12" r="1.4"/><circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="18" r="1.4"/><circle cx="15" cy="18" r="1.4"/></svg></span>`;

/**
 * @param {'season'|'game'} statsMode
 */
export function formatStatLine(player, statsMode) {
  if (statsMode === "season") {
    const s = player?.season_stats || {};
    return [
      { v: Number(s.PPG ?? 0).toFixed(1), l: "PPG" },
      { v: Number(s.RPG ?? 0).toFixed(1), l: "RPG" },
      { v: Number(s.APG ?? 0).toFixed(1), l: "APG" },
      { v: `${Number(s["DEF%"] ?? 0)}%`, l: "DEF" },
    ];
  }
  const g = player?.game_stats || {};
  return [
    { v: String(Number(g.PTS ?? 0)), l: "PTS" },
    { v: String(Number(g.REB ?? 0)), l: "REB" },
    { v: String(Number(g.AST ?? 0)), l: "AST" },
    { v: `${Number(g["DEF%"] ?? 0)}%`, l: "DEF" },
  ];
}

/**
 * Build a player tile.
 * RT always lives in a fixed outer gutter (away left / home right) so columns align.
 * @param {'edge'|'none'} rtMode
 */
export function buildPlayerTileHtml(player, {
  side,
  teamColor,
  isUserColumn = false,
  statsMode = "game",
  rtMode = "edge",
  slotIndex = null,
} = {}) {
  const rt = Number(player?.rt ?? 0);
  const jersey = player?.jersey != null && player.jersey !== "" ? String(player.jersey) : "—";
  const height = player?.height || "—";
  const weight = player?.weight != null && player.weight !== "" ? `${player.weight} lb` : "—";
  const name = escapeHtml(player?.name || "Unknown");
  const img = playerImageUrl(player?.player_id);
  const stats = formatStatLine(player, statsMode)
    .map((s) => `<div class="dm-st"><span class="dm-sv">${escapeHtml(s.v)}</span><span class="dm-sl">${s.l}</span></div>`)
    .join("");

  const imgHtml = img
    ? `<img loading="lazy" width="176" height="176" src="${escapeHtml(img)}" alt="${name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';"><div class="dm-sil" style="display:none">${SILHOUETTE}</div>`
    : `<div class="dm-sil">${SILHOUETTE}</div>`;

  const gutterHtml =
    rtMode === "edge"
      ? `<div class="dm-rtgutter"><div class="dm-rtedge" style="color:${rtBadgeBg(rt)}" aria-label="RT ${escapeHtml(formatRtDisplay(rt))}">${escapeHtml(formatRtDisplay(rt))}</div></div>`
      : `<div class="dm-rtgutter" aria-hidden="true"></div>`;

  return `
    <div class="dm-ptile" data-side="${side}" ${isUserColumn ? `data-slot="${slotIndex ?? ""}"` : ""} style="--pc:${escapeHtml(teamColor || "#ffffff")}">
      ${gutterHtml}
      <div class="dm-pbody">
        ${isUserColumn ? DRAG_HINT : ""}
        <div class="dm-ph">${imgHtml}</div>
        <div class="dm-pinfo">
          <div class="dm-nm">${name} <span class="dm-jn">(#${escapeHtml(jersey)})</span> <span class="dm-meta">· ${escapeHtml(height)} · ${escapeHtml(weight)}</span></div>
          <div class="dm-statline">${stats}</div>
        </div>
      </div>
    </div>`;
}

export function favArrowSvg(leftRt, rightRt, leftPrimary, rightPrimary) {
  const d = Number(leftRt) - Number(rightRt);
  if (d >= 3) {
    return `<svg viewBox="0 0 28 24" style="color:${escapeHtml(leftPrimary)}"><path d="M23 12H5 M12 5l-7 7 7 7"/></svg>`;
  }
  if (d <= -3) {
    return `<svg viewBox="0 0 28 24" style="color:${escapeHtml(rightPrimary)}"><path d="M5 12h18 M16 5l7 7-7 7"/></svg>`;
  }
  return `<svg viewBox="0 0 28 24" style="color:#c8ccd6"><path d="M9 5l-6 7 6 7 M19 5l6 7-6 7 M5 12h18"/></svg>`;
}

export function favAccentColor(leftRt, rightRt, leftPrimary, rightPrimary) {
  const d = Number(leftRt) - Number(rightRt);
  if (d >= 3) return leftPrimary;
  if (d <= -3) return rightPrimary;
  return "#c8ccd6";
}

export function applyFavorBorders(leftPh, rightPh, leftRt, rightRt, leftPrimary, rightPrimary) {
  const setBorder = (el, w, c) => {
    if (!el) return;
    el.style.borderWidth = w;
    el.style.borderColor = c;
    el.style.borderStyle = w === "0" ? "none" : "solid";
    const bold = w === "4px";
    el.classList.toggle("dm-bold", bold);
    if (bold) el.style.setProperty("--glow", c);
    else el.style.removeProperty("--glow");
  };
  const diff = Number(leftRt) - Number(rightRt);
  if (Math.abs(diff) <= 2) {
    setBorder(leftPh, "2px", "#ffffff");
    setBorder(rightPh, "2px", "#ffffff");
  } else if (diff >= 3) {
    setBorder(leftPh, "4px", leftPrimary);
    setBorder(rightPh, "0", "transparent");
  } else {
    setBorder(leftPh, "0", "transparent");
    setBorder(rightPh, "4px", rightPrimary);
  }
}

export function userOrderFromMatchups(matchups) {
  const m = matchups && typeof matchups === "object" ? matchups : {};
  return POSITIONS.map((oppPos) => {
    const found = Object.entries(m).find(([, guarded]) => guarded === oppPos);
    return found ? found[0] : oppPos;
  });
}

export function matchupsFromUserOrder(userOrder) {
  const matchups = {};
  (userOrder || POSITIONS).forEach((userPos, i) => {
    matchups[userPos] = POSITIONS[i];
  });
  return matchups;
}

export async function saveManDefenseMatchups(gameId, matchups) {
  const API_CONFIG = window.API_CONFIG;
  if (!API_CONFIG) throw new Error("API_CONFIG not available");
  const response = await fetch(API_CONFIG.buildUrl("/api/save-man-defense-matchups"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...API_CONFIG.getAuthHeaders(),
    },
    body: JSON.stringify({ game_id: gameId, matchups }),
  });
  if (!response.ok) {
    let detail = "Failed to save matchups";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch (_e) {
      // ignore
    }
    throw new Error(detail);
  }
  return true;
}

export function normalizeMatchupsPayload(data) {
  const userTeamSide = data?.user_team_side === "away" ? "away" : "home";
  const home = data?.home_team || (userTeamSide === "home" ? data?.user_team : data?.computer_team);
  const away = data?.away_team || (userTeamSide === "away" ? data?.user_team : data?.computer_team);
  return {
    userTeamSide,
    homeTeam: home || { team_name: "Home", players: [], primary_color: "#1F8A5B", natl_rank: 0, wins: 0, losses: 0 },
    awayTeam: away || { team_name: "Away", players: [], primary_color: "#9E1B32", natl_rank: 0, wins: 0, losses: 0 },
    currentMatchups: data?.current_matchups || matchupsFromUserOrder(POSITIONS),
    isFranchise: !!(data?.is_franchise || data?.franchise_id),
    isTournamentContext: !!data?.is_tournament_context,
    franchiseWeek: data?.franchise_week ?? null,
  };
}

export function playMatchupsUiSfx(filename) {
  if (typeof window !== "undefined" && typeof window.playSound === "function") {
    window.playSound(filename);
  }
}

export function wireUserColumnDrag(root, getOrder, setOrderAndRender) {
  let dragSlot = null;
  root.querySelectorAll(".dm-ptile[data-slot]").forEach((tile) => {
    tile.setAttribute("draggable", "true");
    tile.addEventListener("dragstart", (e) => {
      dragSlot = Number(tile.dataset.slot);
      tile.classList.add("dragging");
      if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
    });
    tile.addEventListener("dragend", () => {
      tile.classList.remove("dragging");
      root.querySelectorAll(".dropcue").forEach((el) => el.classList.remove("dropcue"));
    });
    tile.addEventListener("dragover", (e) => {
      e.preventDefault();
      tile.classList.add("dropcue");
    });
    tile.addEventListener("dragleave", () => tile.classList.remove("dropcue"));
    tile.addEventListener("drop", (e) => {
      e.preventDefault();
      const to = Number(tile.dataset.slot);
      if (dragSlot == null || Number.isNaN(to) || dragSlot === to) return;
      const order = getOrder().slice();
      const tmp = order[dragSlot];
      order[dragSlot] = order[to];
      order[to] = tmp;
      dragSlot = null;
      playMatchupsUiSfx("click-tiny.wav");
      setOrderAndRender(order);
    });
  });
}
