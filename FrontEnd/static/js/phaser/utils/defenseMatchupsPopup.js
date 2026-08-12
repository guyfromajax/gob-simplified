/**
 * Defense Matchups Popup + franchise Q1 pre-game handoff.
 *
 * - Franchise Q1 (Play Quarter): cinematic pre-game experience
 * - All other Play Quarter gates: restyled Strategic Modal (away left / home right)
 * - Tutorial: skipped
 * - Single-game: restyled modal only (no cinematic / no pregame bed)
 */

import { playDefenseMatchupModalCourtSfx } from "./gameSfx.js";
import { showPreGameExperience } from "./preGameExperience.js";
import {
  POSITIONS,
  buildPlayerTileHtml,
  favArrowSvg,
  applyFavorBorders,
  userOrderFromMatchups,
  matchupsFromUserOrder,
  saveManDefenseMatchups,
  wireUserColumnDrag,
  normalizeMatchupsPayload,
  playMatchupsUiSfx,
  readableTeamPresentationColor,
} from "./matchupsUiShared.js";

const SESSION_STORAGE_KEY_PREFIX = "defenseMatchupsDontShow_";
const ANNOUNCE_SESSION_KEY_PREFIX = "defenseMatchupsAnnouncePlayed_";

let dontShowAgainThisGame = false;

function showMatchupsTransitionOverlay() {
  if (typeof window === "undefined") return;
  window.__GOB_DEFENSE_MATCHUPS_TRANSITION_OVERLAY__ = true;
  if (window.PageLoadOverlay && typeof window.PageLoadOverlay.show === "function") {
    window.PageLoadOverlay.show("Loading game...");
  }
}

function hideMatchupsTransitionOverlay() {
  if (typeof window === "undefined") return;
  window.__GOB_DEFENSE_MATCHUPS_TRANSITION_OVERLAY__ = false;
  if (window.PageLoadOverlay && typeof window.PageLoadOverlay.hide === "function") {
    window.PageLoadOverlay.hide();
  }
}

function hasDefenseMatchupAnnouncePlayed(gameId) {
  if (!gameId || typeof sessionStorage === "undefined") return false;
  return sessionStorage.getItem(ANNOUNCE_SESSION_KEY_PREFIX + gameId) === "1";
}

function markDefenseMatchupAnnouncePlayed(gameId) {
  if (!gameId || typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(ANNOUNCE_SESSION_KEY_PREFIX + gameId, "1");
}

function isFranchiseContext(scene, payload) {
  if (payload?.isFranchise) return true;
  if (scene?.franchiseId) return true;
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  return params.get("mode") === "franchise" || !!params.get("franchise_id");
}

function isQ1StartContext(scene, options = {}) {
  if (typeof options.isQ1Start === "boolean") return options.isQ1Start;
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  const resumeFromTimeout = params.get("resume_from_timeout") === "true";
  const activeResume = params.get("active_resume") === "true" || !!scene?.resumeActive;
  return Number(scene?.quarter) === 1 && !resumeFromTimeout && !activeResume;
}

function ensureInGameStyles() {
  if (document.getElementById("defense-matchups-popup-styles")) return;
  const style = document.createElement("style");
  style.id = "defense-matchups-popup-styles";
  style.textContent = `
    .defense-matchups-popup {
      position: fixed; inset: 0; z-index: 10002;
      background: rgba(0, 0, 0, 0.75);
      display: flex; align-items: center; justify-content: center;
      padding: 22px; font-family: Inter, system-ui, sans-serif;
      color: rgba(255,255,255,0.90); -webkit-font-smoothing: antialiased;
    }
    .defense-matchups-content {
      width: min(1000px, 100%); max-height: calc(100% - 24px); overflow: auto;
      background: rgba(18, 22, 32, 0.98); border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px; box-shadow: 0 30px 70px rgba(0,0,0,0.6);
      padding: 22px 26px 20px; animation: dmRise .2s ease;
    }
    @keyframes dmRise { from { transform: scale(.97); opacity: .6; } to { transform: none; opacity: 1; } }
    .dm-m-heads {
      display: grid; grid-template-columns: 1fr 60px 1fr; gap: 0; margin: 0 0 6px;
    }
    .dm-m-head {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: 20px; letter-spacing: .06em; color: #fff;
      text-align: center; padding: 2px 10px 8px; justify-self: stretch;
      background: transparent; border: none; border-bottom: 2px solid var(--head-underline, rgba(255,255,255,0.35));
      border-radius: 0;
    }
    .dm-rows { display: flex; flex-direction: column; }
    .dm-pair {
      display: grid; grid-template-columns: 1fr 60px 1fr; align-items: center;
      position: relative; padding: 14px 0;
    }
    .dm-pair:not(:last-child)::after {
      content: ''; position: absolute; left: 10%; right: 10%; bottom: 0; height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12) 28%, rgba(255,255,255,0.12) 72%, transparent);
    }
    .dm-side-left { justify-self: end; width: 100%; max-width: 440px; }
    .dm-side-right { justify-self: start; width: 100%; max-width: 440px; }
    .dm-ptile {
      display: grid; align-items: center; gap: 8px; position: relative;
      --dm-rt-gutter: 2.75em;
    }
    .dm-ptile[data-side="left"] {
      grid-template-columns: var(--dm-rt-gutter) minmax(0, 1fr);
      text-align: right;
    }
    .dm-ptile[data-side="right"] {
      grid-template-columns: minmax(0, 1fr) var(--dm-rt-gutter);
      text-align: left;
    }
    .dm-ptile[data-side="right"] .dm-rtgutter { order: 2; }
    .dm-ptile[data-side="right"] .dm-pbody { order: 1; }
    .dm-rtgutter {
      display: flex; align-items: center; width: var(--dm-rt-gutter);
      flex-shrink: 0; min-height: 100%;
    }
    .dm-ptile[data-side="left"] .dm-rtgutter { justify-content: flex-start; }
    .dm-ptile[data-side="right"] .dm-rtgutter { justify-content: flex-end; }
    .dm-pbody { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .dm-ptile[data-side="left"] .dm-pbody { flex-direction: row-reverse; }
    .dm-ptile[data-side="right"] .dm-pbody { flex-direction: row; }
    .dm-user-col .dm-ptile {
      cursor: grab; border-radius: 12px; padding: 5px 7px; margin: -5px -7px;
      transition: background .15s, box-shadow .15s;
    }
    .dm-user-col .dm-ptile:hover { background: rgba(255,255,255,0.04); }
    .dm-ptile.dragging { opacity: .45; cursor: grabbing; }
    .dm-ptile.dropcue { background: rgba(255,255,255,0.09); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.3); }
    .dm-draghint { display: flex; color: rgba(255,255,255,0.40); }
    .dm-draghint svg { width: 14px; height: 14px; }
    .dm-ph {
      position: relative; flex-shrink: 0; width: 60px; aspect-ratio: 1/1; border-radius: 12px;
      overflow: hidden; background: linear-gradient(180deg, #1b2130, #10141d);
      border: 2px solid rgba(255,255,255,0.16); box-shadow: 0 6px 16px rgba(0,0,0,0.4);
    }
    .dm-ph img { width: 100%; height: 100%; object-fit: cover; object-position: center top; display: block; }
    .dm-sil { position: absolute; inset: 0; display: flex; align-items: flex-end; justify-content: center; }
    .dm-sil svg { width: 78%; height: 88%; opacity: .8; }
    .dm-rtedge {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif;
      font-size: clamp(22px, 3.2vw, 30px); line-height: 1; letter-spacing: .02em;
      font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;
      width: 100%;
    }
    .dm-ptile[data-side="left"] .dm-rtedge { text-align: left; }
    .dm-ptile[data-side="right"] .dm-rtedge { text-align: right; }
    .dm-ph.dm-bold { animation: dmPulse 1.9s ease-in-out infinite; }
    @keyframes dmPulse {
      0%,100% { box-shadow: 0 6px 16px rgba(0,0,0,0.4), 0 0 5px 1px var(--glow, transparent); }
      50% { box-shadow: 0 6px 16px rgba(0,0,0,0.4), 0 0 13px 3px var(--glow, transparent); }
    }
    @media (prefers-reduced-motion: reduce) { .dm-ph.dm-bold { animation: none; } }
    .dm-pinfo { min-width: 0; }
    .dm-nm { font-size: 14px; font-weight: 700; color: #fff; line-height: 1.1; white-space: nowrap; }
    .dm-jn { color: rgba(255,255,255,0.55); font-weight: 600; font-size: .85em; }
    .dm-meta { color: rgba(255,255,255,0.55); font-weight: 600; font-size: 11px; }
    .dm-statline { margin-top: 5px; display: flex; gap: 11px; font-variant-numeric: tabular-nums; }
    .dm-side-left .dm-statline { justify-content: flex-end; }
    .dm-side-right .dm-statline { justify-content: flex-start; }
    .dm-st { display: flex; flex-direction: column; align-items: center; gap: 1px; }
    .dm-sv { font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.90); }
    .dm-sl { font-size: 8px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; color: rgba(255,255,255,0.40); }
    .dm-vs { display: flex; align-items: center; justify-content: center; }
    .dm-favarrow svg { width: 28px; height: 24px; fill: none; stroke: currentColor; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
    .dm-m-foot {
      margin-top: 18px; display: flex; flex-direction: column; align-items: center; gap: 11px;
    }
    .dm-m-submit {
      width: auto; padding: 0 40px; height: 46px; border: none; border-radius: 10px;
      background: #34EC27; color: #0a1f06; font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: 20px;
      letter-spacing: .06em; cursor: pointer;
      box-shadow: 0 8px 22px rgba(52,236,39,0.26), inset 0 1px 0 rgba(255,255,255,0.35);
      transition: filter .15s, transform .1s;
    }
    .dm-m-submit:hover { filter: brightness(1.06); }
    .dm-m-submit:active { transform: translateY(1px); }
    .dm-dontshow {
      display: inline-flex; align-items: center; gap: 8px; font-size: 12px;
      color: rgba(255,255,255,0.55); cursor: pointer; user-select: none;
    }
    .dm-dontshow input {
      appearance: none; width: 16px; height: 16px; border-radius: 4px;
      border: 1.5px solid rgba(255,255,255,0.40); display: grid; place-items: center; cursor: pointer;
    }
    .dm-dontshow input:checked { background: #F79420; border-color: #F79420; }
    .dm-dontshow input:checked::after { content: '✓'; color: #15181f; font-size: 11px; font-weight: 900; }
    @media (max-width: 640px) {
      .dm-statline { gap: 7px; }
      .dm-sv { font-size: 11px; }
      .dm-pair, .dm-m-heads { grid-template-columns: 1fr 44px 1fr; }
      .dm-ptile { --dm-rt-gutter: 2.4em; }
      .dm-rtedge { font-size: 20px; }
    }
  `;
  document.head.appendChild(style);
}

function showInGameMatchupsModal(gameId, scene, normalized, resolve) {
  ensureInGameStyles();
  const existing = document.querySelector(".defense-matchups-popup");
  if (existing) existing.remove();

  const { userTeamSide, homeTeam, awayTeam, currentMatchups } = normalized;
  const homeChrome =
    typeof lookupTeamChrome === "function"
      ? lookupTeamChrome(homeTeam?.team_name || homeTeam?.name || homeTeam?.display_name, homeTeam)
      : null;
  const awayChrome =
    typeof lookupTeamChrome === "function"
      ? lookupTeamChrome(awayTeam?.team_name || awayTeam?.name || awayTeam?.display_name, awayTeam)
      : null;
  const homePrimary = readableTeamPresentationColor(
    homeChrome?.primary_color || homeTeam.primary_color || "#1F8A5B",
    homeChrome?.secondary_color || homeTeam.secondary_color
  );
  const awayPrimary = readableTeamPresentationColor(
    awayChrome?.primary_color || awayTeam.primary_color || "#9E1B32",
    awayChrome?.secondary_color || awayTeam.secondary_color
  );
  const homeLabel = homeChrome?.label || homeTeam.display_name || homeTeam.team_name || "Home";
  const awayLabel = awayChrome?.label || awayTeam.display_name || awayTeam.team_name || "Away";
  const userIsHome = userTeamSide === "home";
  let userOrder = userOrderFromMatchups(currentMatchups);

  const popup = document.createElement("div");
  popup.className = "defense-matchups-popup";
  popup.innerHTML = `
    <div class="defense-matchups-content" role="dialog" aria-label="Defense Matchups">
      <div class="dm-m-heads">
        <div class="dm-m-head" style="--head-underline:${awayPrimary}">${awayLabel}</div>
        <div></div>
        <div class="dm-m-head" style="--head-underline:${homePrimary}">${homeLabel}</div>
      </div>
      <div class="dm-rows"></div>
      <div class="dm-m-foot">
        <button type="button" class="dm-m-submit">Submit Defense Matchups</button>
        <label class="dm-dontshow"><input type="checkbox" id="dont-show-again-checkbox"> Don't show this pop up again this game</label>
      </div>
    </div>
  `;
  document.body.appendChild(popup);

  const rows = popup.querySelector(".dm-rows");

  function playerByPos(team, pos) {
    return (team.players || []).find((p) => p.position === pos) || null;
  }

  function render() {
    rows.innerHTML = POSITIONS.map((pos, i) => `
      <div class="dm-pair" data-slot="${i}">
        <div class="dm-side-left ${userIsHome ? "" : "dm-user-col"}"></div>
        <div class="dm-vs"><span class="dm-favarrow"></span></div>
        <div class="dm-side-right ${userIsHome ? "dm-user-col" : ""}"></div>
      </div>
    `).join("");

    rows.querySelectorAll(".dm-pair").forEach((row, i) => {
      const oppPos = POSITIONS[i];
      const userPos = userOrder[i];
      // Court convention: away left / home right (user column follows userTeamSide).
      const leftP = userIsHome
        ? playerByPos(awayTeam, oppPos)
        : playerByPos(awayTeam, userPos);
      const rightP = userIsHome
        ? playerByPos(homeTeam, userPos)
        : playerByPos(homeTeam, oppPos);

      const leftEl = row.querySelector(".dm-side-left");
      const rightEl = row.querySelector(".dm-side-right");
      leftEl.innerHTML = leftP
        ? buildPlayerTileHtml(leftP, {
            side: "left",
            teamColor: awayPrimary,
            isUserColumn: !userIsHome,
            statsMode: "game",
            rtMode: "edge",
            slotIndex: userIsHome ? null : i,
          })
        : "";
      rightEl.innerHTML = rightP
        ? buildPlayerTileHtml(rightP, {
            side: "right",
            teamColor: homePrimary,
            isUserColumn: userIsHome,
            statsMode: "game",
            rtMode: "edge",
            slotIndex: userIsHome ? i : null,
          })
        : "";

      const leftRt = Number(leftP?.rt ?? 0);
      const rightRt = Number(rightP?.rt ?? 0);
      applyFavorBorders(
        leftEl.querySelector(".dm-ph"),
        rightEl.querySelector(".dm-ph"),
        leftRt,
        rightRt,
        awayPrimary,
        homePrimary
      );
      row.querySelector(".dm-favarrow").innerHTML = favArrowSvg(
        leftRt,
        rightRt,
        awayPrimary,
        homePrimary
      );
    });

    wireUserColumnDrag(
      popup,
      () => userOrder,
      (next) => {
        userOrder = next;
        render();
      }
    );
  }

  render();

  if (!hasDefenseMatchupAnnouncePlayed(gameId)) {
    playDefenseMatchupModalCourtSfx(scene);
    markDefenseMatchupAnnouncePlayed(gameId);
  }

  popup.querySelector("#dont-show-again-checkbox")?.addEventListener("change", () => {
    playMatchupsUiSfx("click-tiny.wav");
  });

  popup.querySelector(".dm-m-submit").addEventListener("click", async () => {
    const checkbox = popup.querySelector("#dont-show-again-checkbox");
    playMatchupsUiSfx("confirm-1-lowervol.wav");
    try {
      await saveManDefenseMatchups(gameId, matchupsFromUserOrder(userOrder));
      if (checkbox?.checked && gameId && typeof sessionStorage !== "undefined") {
        dontShowAgainThisGame = true;
        sessionStorage.setItem(SESSION_STORAGE_KEY_PREFIX + gameId, "1");
      }
      popup.remove();
      resolve();
    } catch (error) {
      console.error("❌ DEFENSE MATCHUPS: Failed to save:", error);
      alert(`Failed to save matchups: ${error.message}`);
    }
  });
}

/**
 * Show defense matchups UI (cinematic or modal).
 * @param {string} gameId
 * @param {Object} scene
 * @param {{ isQ1Start?: boolean }} [options]
 */
export async function showDefenseMatchupsPopup(gameId, scene, options = {}) {
  if (typeof window !== "undefined") {
    const urlMode = new URLSearchParams(window.location.search).get("mode");
    if (urlMode === "tutorial") {
      return;
    }
  }

  const persisted =
    typeof sessionStorage !== "undefined" &&
    gameId &&
    sessionStorage.getItem(SESSION_STORAGE_KEY_PREFIX + gameId) === "1";
  if (dontShowAgainThisGame || persisted) {
    return;
  }

  const existingPopup = document.querySelector(".defense-matchups-popup");
  if (existingPopup) existingPopup.remove();
  const existingPregame = document.querySelector(".pgxp-root");
  if (existingPregame) existingPregame.remove();

  return new Promise((resolve) => {
    try {
      const API_CONFIG = window.API_CONFIG;
      if (!API_CONFIG) {
        console.error("❌ DEFENSE MATCHUPS: API_CONFIG not available");
        resolve();
        return;
      }

      fetch(API_CONFIG.buildUrl(`/api/game/${gameId}/lineup-for-matchups`), {
        headers: API_CONFIG.getAuthHeaders(),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch lineup data: ${response.statusText}`);
          }
          return response.json();
        })
        .then(async (data) => {
          const normalized = normalizeMatchupsPayload(data);
          const franchise = isFranchiseContext(scene, normalized);
          const q1 = isQ1StartContext(scene, options);

          if (franchise && q1) {
            await showPreGameExperience(gameId, scene, normalized);
            resolve();
            return;
          }

          showInGameMatchupsModal(gameId, scene, normalized, resolve);
        })
        .catch((error) => {
          console.error("❌ DEFENSE MATCHUPS: Failed to show popup:", error);
          resolve();
        });
    } catch (error) {
      console.error("❌ DEFENSE MATCHUPS: Failed to show popup:", error);
      resolve();
    }
  });
}

/**
 * Reset "don't show again" for a new game so the popup can show at Q1 start.
 */
export function resetDontShowAgainFlag(gameId) {
  dontShowAgainThisGame = false;
  if (typeof sessionStorage !== "undefined" && gameId) {
    sessionStorage.removeItem(SESSION_STORAGE_KEY_PREFIX + gameId);
    sessionStorage.removeItem(ANNOUNCE_SESSION_KEY_PREFIX + gameId);
  }
}

// Keep overlay helpers available for any callers that imported them historically.
export { showMatchupsTransitionOverlay, hideMatchupsTransitionOverlay };
