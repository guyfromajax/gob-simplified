function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function normalizeTeamName(name) {
  if (!name) return '';
  return String(name).trim().toLowerCase();
}

function canonicalTeamName(name) {
  if (!name) return '';
  return String(name).replace(/-/g, '_').replace(/\s+/g, '_').toUpperCase();
}

function resolvePrimaryColor(teamObj, fallback = '#1a1a2e') {
  return teamObj?.colors?.primary_color || teamObj?.primary_color || fallback;
}

function getTeamContext(gameData, scoreOverride = null) {
  const homeTeamId = gameData?.home_team_id || '';
  const awayTeamId = gameData?.away_team_id || '';
  const teamsObj = gameData?.teams || {};
  const homeTeamObj = homeTeamId && teamsObj[homeTeamId] ? teamsObj[homeTeamId] : (gameData?.home_team || {});
  const awayTeamObj = awayTeamId && teamsObj[awayTeamId] ? teamsObj[awayTeamId] : (gameData?.away_team || {});

  const homeTeamName = homeTeamObj?.name || gameData?.home_team?.name || 'Home Team';
  const awayTeamName = awayTeamObj?.name || gameData?.away_team?.name || 'Away Team';

  const scoreSource = scoreOverride || gameData?.score || {};
  const homeScore = toNumber(scoreSource[homeTeamName] ?? homeTeamObj?.score ?? 0);
  const awayScore = toNumber(scoreSource[awayTeamName] ?? awayTeamObj?.score ?? 0);

  let winningTeam = null;
  if (homeScore > awayScore) winningTeam = 'home';
  else if (awayScore > homeScore) winningTeam = 'away';

  return {
    homeTeamId,
    awayTeamId,
    homeTeamName,
    awayTeamName,
    homeScore,
    awayScore,
    winningTeam,
    homePrimaryColor: resolvePrimaryColor(homeTeamObj),
    awayPrimaryColor: resolvePrimaryColor(awayTeamObj),
  };
}

function inferTeamFromBoxScoreKey(key, teamCtx) {
  const homeNames = new Set([
    teamCtx.homeTeamId,
    teamCtx.homeTeamName,
    canonicalTeamName(teamCtx.homeTeamName),
    normalizeTeamName(teamCtx.homeTeamName),
  ].filter(Boolean));
  const awayNames = new Set([
    teamCtx.awayTeamId,
    teamCtx.awayTeamName,
    canonicalTeamName(teamCtx.awayTeamName),
    normalizeTeamName(teamCtx.awayTeamName),
  ].filter(Boolean));

  if (homeNames.has(key) || homeNames.has(normalizeTeamName(key))) return 'home';
  if (awayNames.has(key) || awayNames.has(normalizeTeamName(key))) return 'away';
  return null;
}

function getPlayerImage(player) {
  const id = player.playerId || player._id || player.player_id || '';
  return player.photo || (id ? `/images/players/${id}.png` : '/images/players/default.png');
}

function buildCandidates(gameData, scoreOverride = null) {
  const teamCtx = getTeamContext(gameData, scoreOverride);
  const map = new Map();

  function upsert(raw, fallbackTeam = null) {
    if (!raw || typeof raw !== 'object') return;
    const stats = raw.stats?.game || raw.stats || raw;
    const name = raw.name || 'Unknown';
    const playerId = raw.playerId || raw.player_id || raw._id || `${fallbackTeam || 'unknown'}:${name}`;
    const key = `${playerId}:${fallbackTeam || raw.team || 'unknown'}`;

    const existing = map.get(key) || {
      playerId,
      name,
      team: fallbackTeam || raw.team || 'unknown',
      teamName: fallbackTeam === 'home' ? teamCtx.homeTeamName : (fallbackTeam === 'away' ? teamCtx.awayTeamName : 'Unknown Team'),
      teamColor: fallbackTeam === 'home' ? teamCtx.homePrimaryColor : (fallbackTeam === 'away' ? teamCtx.awayPrimaryColor : '#1a1a2e'),
      photo: getPlayerImage(raw),
      stats: {},
    };

    existing.name = raw.name || existing.name;
    existing.photo = raw.photo || existing.photo;
    if (fallbackTeam) {
      existing.team = fallbackTeam;
      existing.teamName = fallbackTeam === 'home' ? teamCtx.homeTeamName : teamCtx.awayTeamName;
      existing.teamColor = fallbackTeam === 'home' ? teamCtx.homePrimaryColor : teamCtx.awayPrimaryColor;
    } else if (raw.team === 'home' || raw.team === 'away') {
      existing.team = raw.team;
      existing.teamName = raw.team === 'home' ? teamCtx.homeTeamName : teamCtx.awayTeamName;
      existing.teamColor = raw.team === 'home' ? teamCtx.homePrimaryColor : teamCtx.awayPrimaryColor;
    }
    existing.stats = { ...existing.stats, ...stats };

    map.set(key, existing);
  }

  const players = Array.isArray(gameData?.players) ? gameData.players : [];
  players.forEach((player) => upsert(player, (player?.team === 'home' || player?.team === 'away') ? player.team : null));

  const boxScore = gameData?.box_score || {};
  Object.entries(boxScore).forEach(([teamKey, teamPlayers]) => {
    const inferredTeam = inferTeamFromBoxScoreKey(teamKey, teamCtx);
    if (!teamPlayers || typeof teamPlayers !== 'object') return;
    Object.values(teamPlayers).forEach((playerData) => {
      if (playerData && typeof playerData === 'object' && playerData.name) {
        upsert(playerData, inferredTeam);
      }
    });
  });

  return { candidates: Array.from(map.values()), teamCtx };
}

function calculatePotgPoints(player) {
  const stats = player.stats || {};
  const pts = toNumber(stats.PTS);
  const ast = toNumber(stats.AST);
  const reb = toNumber(stats.REB) || (toNumber(stats.OREB) + toNumber(stats.DREB));
  const stl = toNumber(stats.STL);
  const blk = toNumber(stats.BLK);
  const defA = toNumber(stats.DEF_A);
  const defS = toNumber(stats.DEF_S);
  const defPct = defA > 0 ? Math.round((defS / defA) * 100) : 0;

  let score = 2 * (pts + ast + reb + stl + blk);
  if (defA > 10) {
    if (defPct > 80) score += 15;
    else if (defPct > 60) score += 10;
    else if (defPct > 40) score += 5;
  }

  return {
    score,
    pts,
    reb,
    ast,
    stl,
    blk,
    defA,
    defPct,
  };
}

function seedFromString(seedText) {
  let hash = 2166136261;
  const text = String(seedText || 'potg-seed');
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seededRandom(seedText) {
  let state = seedFromString(seedText) || 1;
  return function next() {
    state += 0x6D2B79F5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pickWeighted(candidates, rng) {
  const total = candidates.reduce((sum, item) => sum + item.weight, 0);
  if (total <= 0) return candidates[0];

  const target = rng() * total;
  let running = 0;
  for (const item of candidates) {
    running += item.weight;
    if (target <= running) return item;
  }
  return candidates[candidates.length - 1];
}

export function calculatePlayerOfTheGame(gameData, options = {}) {
  if (!gameData || typeof gameData !== 'object') return null;

  const { gameId = '', scoreOverride = null } = options;
  const { candidates, teamCtx } = buildCandidates(gameData, scoreOverride);
  if (!candidates.length) return null;

  const scored = candidates.map((player) => ({
    ...player,
    ...calculatePotgPoints(player),
  })).sort((a, b) => b.score - a.score);

  const top = scored[0];
  const second = scored[1] || null;
  let winner = top;

  if (second && (top.score - second.score) < 16) {
    const cutoff = second.score;
    const contenders = scored.filter((p) => p.score >= cutoff);

    const winners = contenders.filter((p) => p.team === teamCtx.winningTeam);
    const losers = contenders.filter((p) => p.team && p.team !== teamCtx.winningTeam);

    let weighted = [];
    if (teamCtx.winningTeam && winners.length > 0 && losers.length > 0) {
      const winnerWeight = 0.67 / winners.length;
      const loserWeight = 0.33 / losers.length;
      weighted = [
        ...winners.map((p) => ({ ...p, weight: winnerWeight })),
        ...losers.map((p) => ({ ...p, weight: loserWeight })),
      ];
    } else {
      const equalWeight = 1 / contenders.length;
      weighted = contenders.map((p) => ({ ...p, weight: equalWeight }));
    }

    const rng = seededRandom(`${gameId || 'no-game-id'}:potg`);
    winner = pickWeighted(weighted, rng);
  }

  return {
    playerId: winner.playerId,
    name: winner.name,
    team: winner.team,
    teamName: winner.teamName,
    teamColor: winner.teamColor || '#1a1a2e',
    photo: winner.photo,
    potgPoints: winner.score,
    stats: {
      pts: winner.pts,
      reb: winner.reb,
      ast: winner.ast,
      stl: winner.stl,
      blk: winner.blk,
      defPct: winner.defPct,
      defA: winner.defA,
    },
  };
}
