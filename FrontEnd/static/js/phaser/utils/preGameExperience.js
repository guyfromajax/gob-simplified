/**
 * Franchise Q1 pre-game experience: starting-five reveal → defense matchups → tip-off.
 */

import {
  startPregameBed,
  stopPregameBed,
  playPregameRevealClick,
} from "./gameSfx.js";
import {
  POSITIONS,
  buildPlayerTileHtml,
  favArrowSvg,
  favAccentColor,
  applyFavorBorders,
  userOrderFromMatchups,
  matchupsFromUserOrder,
  saveManDefenseMatchups,
  wireUserColumnDrag,
  playMatchupsUiSfx,
  escapeHtml,
} from "./matchupsUiShared.js";

const SKIP_INTRO_KEY_PREFIX = "pregameSkipIntro_";
const DONT_SHOW_KEY_PREFIX = "defenseMatchupsDontShow_";

function ensureStyles() {
  if (document.getElementById("pre-game-xp-styles")) return;
  const style = document.createElement("style");
  style.id = "pre-game-xp-styles";
  style.textContent = `
    .pgxp-root {
      position: fixed; inset: 0; z-index: 10002;
      background:
        radial-gradient(120% 80% at 50% 42%, rgba(39,64,142,0.12), transparent 62%),
        radial-gradient(90% 60% at 50% 120%, rgba(247,148,32,0.05), transparent 60%),
        #0b0d14;
      display: flex; flex-direction: column; isolation: isolate;
      color: rgba(255,255,255,0.90); font-family: Inter, system-ui, sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    .pgxp-root::before {
      content: ''; position: absolute; left: 50%; bottom: -46%;
      width: 92%; aspect-ratio: 1/1; transform: translateX(-50%);
      border-radius: 50%; border: 1px solid rgba(255,255,255,0.05);
      box-shadow: 0 0 0 1px rgba(255,255,255,0.02); pointer-events: none;
    }
    .pgxp-head { position: relative; z-index: 3; text-align: center; padding: 26px 20px 4px; flex-shrink: 0; }
    .pgxp-title {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: clamp(34px, 5vw, 60px); line-height: .92;
      letter-spacing: .02em; color: #fff;
      opacity: 0; transform: translateY(-8px);
      transition: opacity .5s ease, transform .5s ease;
    }
    .pgxp-root[data-phase] .pgxp-title { opacity: 1; transform: none; }
    .pgxp-records {
      margin-top: 10px; display: inline-flex; align-items: center; justify-content: center; gap: 0;
      opacity: 0; transition: opacity .45s ease .08s;
    }
    .pgxp-root[data-phase] .pgxp-records { opacity: 1; }
    .pgxp-root[data-phase="matchups"] .pgxp-records { display: none; }
    .pgxp-rec {
      display: inline-flex; align-items: baseline; gap: 8px; padding: 0 18px;
      font-variant-numeric: tabular-nums;
    }
    .pgxp-rec .rk {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: clamp(22px, 2.8vw, 30px);
      line-height: 1; letter-spacing: .02em; color: #fff;
    }
    .pgxp-rec .wl {
      font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.45); letter-spacing: .02em;
    }
    .pgxp-rec-div {
      width: 1px; height: 22px; background: rgba(255,255,255,0.18); flex-shrink: 0;
    }
    .pgxp-board {
      position: relative; z-index: 2; flex: 1; min-height: 0;
      display: flex; flex-direction: column; justify-content: center;
      gap: 18px; padding: 8px clamp(14px, 4vw, 54px) 8px;
      max-width: 1200px; width: 100%; margin: 0 auto;
    }
    .pgxp-pair {
      display: grid; grid-template-columns: 1fr 68px 1fr; align-items: center;
      position: relative; opacity: 0;
      transition: opacity .45s ease, filter .45s ease;
    }
    .pgxp-pair:not(:last-child)::after {
      content: ''; position: absolute; left: 12%; right: 12%; bottom: -9px; height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12) 30%, rgba(255,255,255,0.12) 70%, transparent);
    }
    .pgxp-pair .pgxp-side-left { transform: translateX(-40px); transition: transform .55s cubic-bezier(.2,.7,.2,1); justify-self: end; width: 100%; max-width: 520px; }
    .pgxp-pair .pgxp-side-right { transform: translateX(40px); transition: transform .55s cubic-bezier(.2,.7,.2,1); justify-self: start; width: 100%; max-width: 520px; }
    .pgxp-pair .pgxp-vs { transform: scale(.4); opacity: 0; transition: transform .4s cubic-bezier(.2,.9,.3,1.3) .1s, opacity .4s ease .1s; }
    .pgxp-pair.in { opacity: 1; }
    .pgxp-pair.in .pgxp-side-left, .pgxp-pair.in .pgxp-side-right { transform: none; }
    .pgxp-pair.in .pgxp-vs { transform: none; opacity: 1; }
    .pgxp-board.revealing .pgxp-pair.in:not(.spot) { filter: brightness(.62) saturate(.85); }
    .pgxp-pair.spot .pgxp-side-left, .pgxp-pair.spot .pgxp-side-right {
      animation: pgxpPairPop .5s cubic-bezier(.2,.8,.3,1.2);
    }
    @keyframes pgxpPairPop { 0%{ transform: scale(1);} 40%{ transform: scale(1.035);} 100%{ transform: scale(1);} }
    .dm-ph.dm-bold { animation: pgxpBorderPulse 1.9s ease-in-out infinite; }
    @keyframes pgxpBorderPulse {
      0%,100% { box-shadow: 0 8px 20px rgba(0,0,0,0.4), 0 0 6px 1px var(--glow, transparent); }
      50% { box-shadow: 0 8px 20px rgba(0,0,0,0.4), 0 0 15px 4px var(--glow, transparent); }
    }
    @media (prefers-reduced-motion: reduce) {
      .dm-ph.dm-bold { animation: none; }
      .pgxp-pair.spot .pgxp-side-left, .pgxp-pair.spot .pgxp-side-right { animation: none; }
    }

    .dm-ptile {
      display: grid; align-items: center; gap: 10px; position: relative;
      --dm-rt-gutter: 3.4em;
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
    .dm-pbody { display: flex; align-items: center; gap: 13px; min-width: 0; }
    .dm-ptile[data-side="left"] .dm-pbody { flex-direction: row-reverse; justify-content: flex-start; }
    .dm-ptile[data-side="right"] .dm-pbody { flex-direction: row; justify-content: flex-start; }
    .dm-ph {
      position: relative; flex-shrink: 0; width: clamp(64px, 7vw, 88px); aspect-ratio: 1/1; border-radius: 14px;
      overflow: hidden; background: linear-gradient(180deg, #1b2130, #10141d);
      border: 2px solid rgba(255,255,255,0.16); box-shadow: 0 8px 20px rgba(0,0,0,0.4);
    }
    .dm-ph img { width: 100%; height: 100%; object-fit: cover; object-position: center top; display: block; }
    .dm-sil { position: absolute; inset: 0; display: flex; align-items: flex-end; justify-content: center; }
    .dm-sil svg { width: 78%; height: 88%; opacity: .8; }
    .dm-rtedge {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif;
      font-size: clamp(28px, 4.2vw, 44px); line-height: 1; letter-spacing: .02em;
      font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;
      width: 100%;
    }
    .dm-ptile[data-side="left"] .dm-rtedge { text-align: left; }
    .dm-ptile[data-side="right"] .dm-rtedge { text-align: right; }
    .dm-pinfo { min-width: 0; }
    .dm-nm { font-size: clamp(13px, 1.5vw, 16px); font-weight: 700; color: #fff; line-height: 1.1; white-space: nowrap; }
    .dm-jn { color: rgba(255,255,255,0.55); font-weight: 600; font-size: .85em; }
    .dm-meta { color: rgba(255,255,255,0.55); font-weight: 600; font-size: 11.5px; }
    .dm-statline { margin-top: 6px; display: flex; gap: 12px; font-variant-numeric: tabular-nums; }
    .pgxp-side-left .dm-statline { justify-content: flex-end; }
    .pgxp-side-right .dm-statline { justify-content: flex-start; }
    .dm-st { display: flex; flex-direction: column; align-items: center; gap: 1px; }
    .dm-sv { font-size: 12.5px; font-weight: 700; color: rgba(255,255,255,0.90); }
    .dm-sl { font-size: 8px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; color: rgba(255,255,255,0.40); }
    .pgxp-vs { display: flex; flex-direction: column; align-items: center; gap: 5px; }
    .pgxp-vstext {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: 20px; line-height: 1; letter-spacing: .06em;
    }
    .pgxp-root[data-phase="matchups"] .pgxp-vstext { display: none; }
    .dm-favarrow { display: flex; }
    .dm-favarrow svg { width: 32px; height: 26px; fill: none; stroke: currentColor; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
    .pgxp-root[data-phase="matchups"] .pgxp-user .dm-ptile {
      cursor: grab; border-radius: 14px; padding: 6px 8px; margin: -6px -8px;
      transition: background .15s, box-shadow .15s;
    }
    .pgxp-root[data-phase="matchups"] .pgxp-user .dm-ptile:hover { background: rgba(255,255,255,0.04); }
    .dm-ptile.dragging { opacity: .45; cursor: grabbing; }
    .dm-ptile.dropcue { background: rgba(255,255,255,0.09); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.3); }
    .dm-draghint { display: none; color: rgba(255,255,255,0.40); }
    .pgxp-root[data-phase="matchups"] .pgxp-user .dm-draghint { display: flex; }
    .dm-draghint svg { width: 15px; height: 15px; }
    .pgxp-foot {
      position: relative; z-index: 4; flex-shrink: 0;
      display: flex; flex-direction: column-reverse; align-items: center; gap: 12px;
      padding: 14px 22px 22px; min-height: 74px;
    }
    .pgxp-cta {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: 22px; letter-spacing: .06em; line-height: 1;
      height: 50px; padding: 0 34px; border-radius: 10px; border: none;
      background: #34EC27; color: #0a1f06; cursor: pointer;
      box-shadow: 0 10px 26px rgba(52,236,39,0.28), inset 0 1px 0 rgba(255,255,255,0.35);
      opacity: 0; transform: translateY(10px) scale(.98); pointer-events: none;
      transition: opacity .4s ease, transform .4s ease, filter .15s;
    }
    .pgxp-cta.show { opacity: 1; transform: none; pointer-events: auto; }
    .pgxp-cta:hover { filter: brightness(1.06); transform: translateY(-1px); }
    .pgxp-cta:active { transform: translateY(1px); }
    .pgxp-dontshow {
      display: none; align-items: center; gap: 8px; font-size: 12px; color: rgba(255,255,255,0.55);
      cursor: pointer; user-select: none;
    }
    .pgxp-root[data-phase="matchups"] .pgxp-dontshow { display: inline-flex; }
    .pgxp-dontshow input {
      appearance: none; width: 16px; height: 16px; border-radius: 4px;
      border: 1.5px solid rgba(255,255,255,0.40); display: grid; place-items: center; cursor: pointer;
    }
    .pgxp-dontshow input:checked { background: #F79420; border-color: #F79420; }
    .pgxp-dontshow input:checked::after { content: '✓'; color: #15181f; font-size: 11px; font-weight: 900; }
    .pgxp-skip {
      position: absolute; right: 20px; bottom: 18px; z-index: 6;
      display: inline-flex; align-items: center; gap: 7px;
      font-size: 11.5px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
      color: rgba(255,255,255,0.40); background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 8px 13px; cursor: pointer;
    }
    .pgxp-skip:hover { color: rgba(255,255,255,0.90); border-color: rgba(255,255,255,0.28); }
    .pgxp-skip svg { width: 14px; height: 14px; }
    .pgxp-root[data-phase="matchups"] .pgxp-skip,
    .pgxp-root[data-phase="tipoff"] .pgxp-skip { display: none; }
    .pgxp-tipoff {
      position: absolute; inset: 0; z-index: 8; display: flex; align-items: center; justify-content: center;
      background: radial-gradient(60% 60% at 50% 50%, rgba(52,236,39,0.14), rgba(5,6,10,0.96));
      opacity: 0; pointer-events: none; transition: opacity .4s ease;
    }
    .pgxp-root[data-phase="tipoff"] .pgxp-tipoff { opacity: 1; }
    .pgxp-tipoff .to {
      font-family: 'Bebas Neue', 'Bebas Neue Pro', sans-serif; font-size: clamp(48px, 9vw, 120px); letter-spacing: .04em; color: #fff;
      text-shadow: 0 0 40px rgba(52,236,39,0.4);
      transform: scale(.8); transition: transform .5s cubic-bezier(.2,.9,.3,1.2);
    }
    .pgxp-root[data-phase="tipoff"] .pgxp-tipoff .to { transform: none; }
    .pgxp-root.dissolved .pgxp-tipoff { opacity: 0; }
    @media (max-width: 720px) {
      .dm-statline { gap: 7px; }
      .dm-sv { font-size: 11px; }
      .pgxp-pair { grid-template-columns: 1fr 50px 1fr; }
      .dm-ptile { --dm-rt-gutter: 2.8em; }
      .dm-rtedge { font-size: 24px; }
    }
  `;
  document.head.appendChild(style);
}

function recordsStripHtml(awayTeam, homeTeam) {
  const aRank = Number(awayTeam?.natl_rank ?? 0);
  const hRank = Number(homeTeam?.natl_rank ?? 0);
  const aW = Number(awayTeam?.wins ?? 0);
  const aL = Number(awayTeam?.losses ?? 0);
  const hW = Number(homeTeam?.wins ?? 0);
  const hL = Number(homeTeam?.losses ?? 0);
  return `
    <div class="pgxp-rec">
      <span class="rk">#${escapeHtml(String(aRank))}</span>
      <span class="wl">${escapeHtml(String(aW))}-${escapeHtml(String(aL))}</span>
    </div>
    <div class="pgxp-rec-div" aria-hidden="true"></div>
    <div class="pgxp-rec">
      <span class="rk">#${escapeHtml(String(hRank))}</span>
      <span class="wl">${escapeHtml(String(hW))}-${escapeHtml(String(hL))}</span>
    </div>`;
}

export function showPreGameExperience(gameId, scene, normalized) {
  ensureStyles();
  const existing = document.querySelector(".pgxp-root");
  if (existing) existing.remove();

  const { userTeamSide, homeTeam, awayTeam, currentMatchups, isTournamentContext } = normalized;
  const homePrimary = homeTeam.primary_color || "#1F8A5B";
  const awayPrimary = awayTeam.primary_color || "#9E1B32";
  const homeName = homeTeam.team_name || "Home";
  const awayName = awayTeam.team_name || "Away";
  const userIsHome = userTeamSide === "home";

  let userOrder = userOrderFromMatchups(currentMatchups);
  const timers = [];
  const clearTimers = () => {
    timers.forEach(clearTimeout);
    timers.length = 0;
  };

  const root = document.createElement("div");
  root.className = "pgxp-root";
  root.innerHTML = `
    <div class="pgxp-head">
      <div class="pgxp-title"></div>
      <div class="pgxp-records">${recordsStripHtml(awayTeam, homeTeam)}</div>
    </div>
    <div class="pgxp-board"></div>
    <div class="pgxp-foot">
      <label class="pgxp-dontshow"><input type="checkbox" id="pgxp-dont-show"> Don't show this pop up again this game</label>
      <button type="button" class="pgxp-cta">Continue</button>
    </div>
    <button type="button" class="pgxp-skip">Skip Intro
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5l7 7-7 7M13 5l7 7-7 7"></path></svg>
    </button>
    <div class="pgxp-tipoff"><div class="to">TIP OFF</div></div>
  `;
  document.body.appendChild(root);

  const board = root.querySelector(".pgxp-board");
  const title = root.querySelector(".pgxp-title");
  const cta = root.querySelector(".pgxp-cta");
  const dontShow = root.querySelector("#pgxp-dont-show");
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function playerByPos(team, pos) {
    return (team.players || []).find((p) => p.position === pos) || null;
  }

  function isMatchupsPhase() {
    return root.dataset.phase === "matchups";
  }

  function renderBoard() {
    board.innerHTML = POSITIONS.map((pos, i) => `
      <div class="pgxp-pair" data-slot="${i}" data-opp-pos="${pos}">
        <div class="pgxp-side-left ${userIsHome ? "pgxp-user" : "pgxp-opp"}"></div>
        <div class="pgxp-vs">
          <span class="dm-favarrow"></span>
          <span class="pgxp-vstext">${pos}</span>
        </div>
        <div class="pgxp-side-right ${userIsHome ? "pgxp-opp" : "pgxp-user"}"></div>
      </div>`).join("");
    paintSlots();
  }

  function paintSlots() {
    const matchups = isMatchupsPhase();
    const statsMode = matchups ? "game" : "season";
    const rtMode = "edge";

    root.querySelectorAll(".pgxp-pair").forEach((row, i) => {
      const oppPos = POSITIONS[i];
      const userPos = userOrder[i];
      const leftP = userIsHome
        ? playerByPos(homeTeam, userPos)
        : playerByPos(homeTeam, oppPos);
      const rightP = userIsHome
        ? playerByPos(awayTeam, oppPos)
        : playerByPos(awayTeam, userPos);

      const leftEl = row.querySelector(".pgxp-side-left");
      const rightEl = row.querySelector(".pgxp-side-right");
      leftEl.innerHTML = leftP
        ? buildPlayerTileHtml(leftP, {
            side: "left",
            teamColor: homePrimary,
            isUserColumn: userIsHome && matchups,
            statsMode,
            rtMode,
            slotIndex: userIsHome && matchups ? i : null,
          })
        : "";
      rightEl.innerHTML = rightP
        ? buildPlayerTileHtml(rightP, {
            side: "right",
            teamColor: awayPrimary,
            isUserColumn: !userIsHome && matchups,
            statsMode,
            rtMode,
            slotIndex: !userIsHome && matchups ? i : null,
          })
        : "";

      const leftRt = Number(leftP?.rt ?? 0);
      const rightRt = Number(rightP?.rt ?? 0);
      applyFavorBorders(
        leftEl.querySelector(".dm-ph"),
        rightEl.querySelector(".dm-ph"),
        leftRt,
        rightRt,
        homePrimary,
        awayPrimary
      );
      row.querySelector(".dm-favarrow").innerHTML = favArrowSvg(
        leftRt,
        rightRt,
        homePrimary,
        awayPrimary
      );
      const vst = row.querySelector(".pgxp-vstext");
      if (vst) {
        vst.style.color = favAccentColor(leftRt, rightRt, homePrimary, awayPrimary);
      }
    });

    if (matchups) {
      wireUserColumnDrag(
        root,
        () => userOrder,
        (next) => {
          userOrder = next;
          paintSlots();
        }
      );
    }
  }

  function toReveal() {
    clearTimers();
    root.classList.remove("dissolved");
    root.dataset.phase = "reveal";
    title.textContent = `${String(awayName).toUpperCase()}  @  ${String(homeName).toUpperCase()}`;
    cta.classList.remove("show");
    cta.textContent = "Set Defense Matchups";
    board.classList.add("revealing");
    const pairs = [...root.querySelectorAll(".pgxp-pair")];
    pairs.forEach((p) => p.classList.remove("in", "spot"));
    paintSlots();

    if (prefersReduced) {
      pairs.forEach((p) => p.classList.add("in"));
      settle();
      return;
    }

    pairs.forEach((p, i) => {
      timers.push(
        setTimeout(() => {
          pairs.forEach((x) => x.classList.remove("spot"));
          p.classList.add("in", "spot");
          playPregameRevealClick(scene);
        }, 700 + i * 820)
      );
    });
    timers.push(setTimeout(settle, 700 + 5 * 820 + 200));
  }

  function settle() {
    board.classList.remove("revealing");
    root.querySelectorAll(".pgxp-pair").forEach((p) => {
      p.classList.add("in");
      p.classList.remove("spot");
    });
    timers.push(setTimeout(() => cta.classList.add("show"), 350));
  }

  function toMatchups() {
    clearTimers();
    root.dataset.phase = "matchups";
    root.querySelectorAll(".pgxp-pair").forEach((p) => p.classList.add("in"));
    board.classList.remove("revealing");
    title.textContent = "DEFENSE MATCHUPS";
    cta.textContent = "Submit & Tip Off";
    cta.classList.add("show");
    paintSlots();
  }

  function finishAndResolve(resolve) {
    clearTimers();
    root.remove();
    resolve();
  }

  function toTipoff(resolve) {
    clearTimers();
    root.dataset.phase = "tipoff";
    playMatchupsUiSfx("confirm-1-lowervol.wav");
    if (dontShow?.checked && gameId && typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(DONT_SHOW_KEY_PREFIX + gameId, "1");
    }
    const matchups = matchupsFromUserOrder(userOrder);
    saveManDefenseMatchups(gameId, matchups)
      .catch((err) => {
        console.error("❌ PRE-GAME XP: Failed to save matchups:", err);
      })
      .finally(() => {
        timers.push(
          setTimeout(() => {
            root.classList.add("dissolved");
            stopPregameBed();
            timers.push(setTimeout(() => finishAndResolve(resolve), 450));
          }, 1900)
        );
      });
  }

  return new Promise((resolve) => {
    startPregameBed(scene, { tournament: !!isTournamentContext });
    renderBoard();

    const skipPersisted =
      typeof sessionStorage !== "undefined" &&
      gameId &&
      sessionStorage.getItem(SKIP_INTRO_KEY_PREFIX + gameId) === "1";

    if (skipPersisted) toMatchups();
    else toReveal();

    root.querySelector(".pgxp-skip").addEventListener("click", () => {
      if (gameId && typeof sessionStorage !== "undefined") {
        sessionStorage.setItem(SKIP_INTRO_KEY_PREFIX + gameId, "1");
      }
      toMatchups();
    });

    dontShow?.addEventListener("change", () => {
      playMatchupsUiSfx("click-tiny.wav");
    });

    cta.addEventListener("click", () => {
      if (root.dataset.phase === "matchups") toTipoff(resolve);
      else toMatchups();
    });
  });
}
