#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const TEAMS_FILE = path.join(ROOT, "teams/128_teams.txt");
const TEAM_IMAGE_DIR = path.join(ROOT, "FrontEnd/static/images/teams");
const TMP_DIR = path.join(ROOT, "tmp/court-template");
const WORKDIR = path.join(TMP_DIR, "non-a1-court-work");
const LEFT_BASKET_ALPHA = path.join(TMP_DIR, "bt_left_basket_alpha3.png");
const RIGHT_BASKET_ALPHA = path.join(TMP_DIR, "bt_right_basket_alpha3.png");
const LEFT_BACKBOARD_OVERLAY = path.join(TMP_DIR, "bt_left_backboard_support_crop.png");
const RIGHT_BACKBOARD_OVERLAY = path.join(TMP_DIR, "bt_right_backboard_support_crop.png");
const LEFT_RIMNET_OVERLAY = path.join(TMP_DIR, "bt_left_rimnet_overlay.png");
const RIGHT_RIMNET_OVERLAY = path.join(TMP_DIR, "bt_right_rimnet_overlay.png");
const LEFT_PAINT_MASK = path.join(TMP_DIR, "mask_left_paint.png");
const RIGHT_PAINT_MASK = path.join(TMP_DIR, "mask_right_paint.png");
const ASSIGNMENT_REPORT = path.join(TMP_DIR, "non_a1_court_assignments.json");

const CANVAS = { w: 3333, h: 2083 };
const FLOOR = { x1: 75, y1: 60, x2: 3258, y2: 2023 };
const FLOOR_EDGE_TOP_Y = 208;
const FLOOR_EDGE_BOTTOM_Y = 1878;
const THREE_POINT_LEFT = {
  startX: 96,
  controlX: 1120,
  topY: 210,
  bottomY: 1874,
};
const THREE_POINT_RIGHT = {
  startX: 3237,
  controlX: 2213,
  topY: 210,
  bottomY: 1874,
};
const FREE_THROW_LEFT_BBOX = { x1: 684, y1: 859, x2: 1044, y2: 1219, start: 248, end: 112 };
const FREE_THROW_RIGHT_BBOX = { x1: 2288, y1: 859, x2: 2648, y2: 1219, start: 68, end: 292 };
const CENTER = { x: 1666, y: 1042 };
const LANE_LEFT_RECT = { x1: 150, y1: 816, x2: 872, y2: 1262 };
const LANE_RIGHT_RECT = { x1: 2452, y1: 816, x2: 3183, y2: 1262 };
const LANE_OUTSIDE_HASHES_LEFT_X = [458, 558, 658, 758];
const LANE_OUTSIDE_HASHES_RIGHT_X = [2575, 2675, 2775, 2875];
const LANE_OUTSIDE_HASH_TOP = { y1: 782, y2: 816 };
const LANE_OUTSIDE_HASH_BOTTOM = { y1: 1262, y2: 1296 };

const HARDWOOD_TONES = {
  light: "#EAD8C6",
  medium: "#DBB891",
  dark: "#CB9D76",
};

const HARDWOOD_VARIANTS = {
  light_light: { inside: "light", outside: "light", pct: 5 },
  light_medium: { inside: "light", outside: "medium", pct: 10 },
  light_dark: { inside: "light", outside: "dark", pct: 5 },
  medium_light: { inside: "medium", outside: "light", pct: 10 },
  medium_medium: { inside: "medium", outside: "medium", pct: 35 },
  medium_dark: { inside: "medium", outside: "dark", pct: 10 },
  dark_light: { inside: "dark", outside: "light", pct: 5 },
  dark_medium: { inside: "dark", outside: "medium", pct: 10 },
  dark_dark: { inside: "dark", outside: "dark", pct: 10 },
};

const LANE_DISTRIBUTION = {
  primary: 80,
  secondary: 15,
  inside_hardwood: 5,
};

const HALF_CIRCLE_DISTRIBUTION = {
  primary: 45,
  secondary: 45,
  inside_hardwood: 10,
};

const OOB_DISTRIBUTION = {
  primary: 45,
  secondary: 20,
  black: 20,
  outside_hardwood: 10,
  inside_hardwood: 5,
};

const A1_REFERENCE_SLUGS = new Set([
  "bentley_truman",
  "lancaster",
  "four_corners",
  "morristown",
  "ocean_city",
  "little_york",
  "xavien",
  "south_lancaster",
]);

const COLORS = {
  line: "#6e675f",
  rim: "#e35a4a",
  backboardOuter: "#d7dde8",
  backboardInner: "#f6f7fb",
  support: "#1b1b1b",
};

function run(args) {
  execFileSync("magick", args, { stdio: "pipe" });
}

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function slugify(name) {
  return (name || "")
    .trim()
    .toLowerCase()
    .replace(/['.]/g, "")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\s/g, "_");
}

function parseTeams() {
  const raw = readFileSync(TEAMS_FILE, "utf8").split(/\r?\n/);
  const cutoff = raw.findIndex((line) => line.trim() === "prestige_rankings");
  const lines = (cutoff === -1 ? raw : raw.slice(0, cutoff))
    .map((line) => line.trim())
    .filter(Boolean);
  const header = lines[0].split("\t");
  return lines.slice(1).map((line) => {
    const cols = line.split("\t");
    const row = Object.fromEntries(header.map((key, idx) => [key, cols[idx] ?? ""]));
    row.slug = slugify(row.team);
    return row;
  });
}

function getArgValue(flag) {
  const idx = process.argv.indexOf(flag);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

function existingCourtSlugs() {
  const slugs = new Set();
  for (const slug of readdirSync(TEAM_IMAGE_DIR)) {
    const teamDir = path.join(TEAM_IMAGE_DIR, slug);
    const filename = `${slug}_court.jpg`;
    if (existsSync(path.join(teamDir, filename))) slugs.add(slug);
  }
  return slugs;
}

function hashString(input) {
  let h = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function countsFromPercent(total, distribution) {
  const entries = Object.entries(distribution);
  const counts = {};
  let allocated = 0;
  for (const [key, pct] of entries) {
    const count = Math.floor((total * pct) / 100);
    counts[key] = count;
    allocated += count;
  }
  let remainder = total - allocated;
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  let i = 0;
  while (remainder > 0) {
    counts[sorted[i % sorted.length][0]] += 1;
    remainder -= 1;
    i += 1;
  }
  return counts;
}

function assignBuckets(teams, distribution, salt) {
  const ordered = [...teams].sort((a, b) => {
    const ha = hashString(`${salt}:${a.slug}`);
    const hb = hashString(`${salt}:${b.slug}`);
    if (ha !== hb) return ha - hb;
    return a.slug.localeCompare(b.slug);
  });
  const counts = countsFromPercent(ordered.length, distribution);
  const assignments = new Map();
  let cursor = 0;
  for (const [key] of Object.entries(distribution)) {
    const count = counts[key];
    for (let i = 0; i < count; i += 1) {
      assignments.set(ordered[cursor].slug, key);
      cursor += 1;
    }
  }
  return assignments;
}

function hex(value, fallback) {
  const v = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(v) ? v : fallback;
}

function applyMaskedColor({ base, mask, color, outfile }) {
  run([
    base,
    "(",
    mask,
    "-alpha", "off",
    "-fill", color,
    "-opaque", "white",
    "-transparent", "black",
    ")",
    "-compose",
    "Over",
    "-composite",
    outfile,
  ]);
}

function drawWoodBase({ base, outsideWood, insideWood, outfile }) {
  const leftPath = `M ${FLOOR.x1},${FLOOR_EDGE_TOP_Y} L ${THREE_POINT_LEFT.startX},${FLOOR_EDGE_TOP_Y} Q ${THREE_POINT_LEFT.controlX},${THREE_POINT_LEFT.topY} ${THREE_POINT_LEFT.controlX},1042 Q ${THREE_POINT_LEFT.controlX},${THREE_POINT_LEFT.bottomY} ${THREE_POINT_LEFT.startX},${FLOOR_EDGE_BOTTOM_Y} L ${FLOOR.x1},${FLOOR_EDGE_BOTTOM_Y} Z`;
  const rightPath = `M ${FLOOR.x2},${FLOOR_EDGE_TOP_Y} L ${THREE_POINT_RIGHT.startX},${FLOOR_EDGE_TOP_Y} Q ${THREE_POINT_RIGHT.controlX},${THREE_POINT_RIGHT.topY} ${THREE_POINT_RIGHT.controlX},1042 Q ${THREE_POINT_RIGHT.controlX},${THREE_POINT_RIGHT.bottomY} ${THREE_POINT_RIGHT.startX},${FLOOR_EDGE_BOTTOM_Y} L ${FLOOR.x2},${FLOOR_EDGE_BOTTOM_Y} Z`;
  run([
    base,
    "-fill", outsideWood,
    "-stroke", "none",
    "-draw", `rectangle ${FLOOR.x1},${FLOOR.y1} ${FLOOR.x2},${FLOOR.y2}`,
    "-fill", insideWood,
    "-draw", `path '${leftPath}'`,
    "-draw", `path '${rightPath}'`,
    outfile,
  ]);
}

function drawLaneRects({ base, color, outfile }) {
  run([
    base,
    "-fill", color,
    "-stroke", "none",
    "-draw", `rectangle ${LANE_LEFT_RECT.x1},${LANE_LEFT_RECT.y1} ${LANE_LEFT_RECT.x2},${LANE_LEFT_RECT.y2}`,
    "-draw", `rectangle ${LANE_RIGHT_RECT.x1},${LANE_RIGHT_RECT.y1} ${LANE_RIGHT_RECT.x2},${LANE_RIGHT_RECT.y2}`,
    outfile,
  ]);
}

function drawCourtLinework({ base, outfile }) {
  run([
    base,
    "-fill", "none",
    "-stroke", COLORS.line,
    "-strokewidth", "8",
    "-draw", `rectangle ${FLOOR.x1},${FLOOR.y1} ${FLOOR.x2},${FLOOR.y2}`,
    "-draw", `line ${CENTER.x},${FLOOR.y1} ${CENTER.x},${FLOOR.y2}`,
    "-draw", `path 'M ${THREE_POINT_LEFT.startX},${THREE_POINT_LEFT.topY} Q ${THREE_POINT_LEFT.controlX},${THREE_POINT_LEFT.topY} ${THREE_POINT_LEFT.controlX},1042 Q ${THREE_POINT_LEFT.controlX},${THREE_POINT_LEFT.bottomY} ${THREE_POINT_LEFT.startX},${THREE_POINT_LEFT.bottomY}'`,
    "-draw", `path 'M ${THREE_POINT_RIGHT.startX},${THREE_POINT_RIGHT.topY} Q ${THREE_POINT_RIGHT.controlX},${THREE_POINT_RIGHT.topY} ${THREE_POINT_RIGHT.controlX},1042 Q ${THREE_POINT_RIGHT.controlX},${THREE_POINT_RIGHT.bottomY} ${THREE_POINT_RIGHT.startX},${THREE_POINT_RIGHT.bottomY}'`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[0]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[0]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[1]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[1]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[2]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[2]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[3]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[3]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[0]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[0]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[1]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[1]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[2]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[2]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_LEFT_X[3]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_LEFT_X[3]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[0]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[0]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[1]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[1]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[2]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[2]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[3]},${LANE_OUTSIDE_HASH_TOP.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[3]},${LANE_OUTSIDE_HASH_TOP.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[0]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[0]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[1]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[1]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[2]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[2]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    "-draw", `line ${LANE_OUTSIDE_HASHES_RIGHT_X[3]},${LANE_OUTSIDE_HASH_BOTTOM.y1} ${LANE_OUTSIDE_HASHES_RIGHT_X[3]},${LANE_OUTSIDE_HASH_BOTTOM.y2}`,
    outfile,
  ]);
}

function resolveAssignmentColor({ token, primary, secondary, insideWood, outsideWood }) {
  switch (token) {
    case "primary":
      return primary;
    case "secondary":
      return secondary;
    case "inside_hardwood":
      return insideWood;
    case "outside_hardwood":
      return outsideWood;
    case "black":
      return "#050505";
    default:
      throw new Error(`Unknown color token: ${token}`);
  }
}

function renderTeamCourt({ team, hardwoodKey, laneKey, halfCircleKey, oobKey }) {
  const teamDir = path.join(TEAM_IMAGE_DIR, team.slug);
  ensureDir(teamDir);
  ensureDir(WORKDIR);

  const hardwood = HARDWOOD_VARIANTS[hardwoodKey];
  const insideWood = HARDWOOD_TONES[hardwood.inside];
  const outsideWood = HARDWOOD_TONES[hardwood.outside];
  const primary = hex(team.primary_color, "#2a2a2a");
  const secondary = hex(team.secondary_color, "#f2f2f2");
  const laneColor = resolveAssignmentColor({ token: laneKey, primary, secondary, insideWood, outsideWood });
  const halfCircleColor = resolveAssignmentColor({ token: halfCircleKey, primary, secondary, insideWood, outsideWood });
  const oobColor = resolveAssignmentColor({ token: oobKey, primary, secondary, insideWood, outsideWood });

  const base = path.join(WORKDIR, `${team.slug}_base.jpg`);
  const withWood = path.join(WORKDIR, `${team.slug}_with_wood.jpg`);
  const withHalfLeft = path.join(WORKDIR, `${team.slug}_with_half_left.jpg`);
  const withBothHalf = path.join(WORKDIR, `${team.slug}_with_both_half.jpg`);
  const withLanes = path.join(WORKDIR, `${team.slug}_with_lanes.jpg`);
  const leftPaintOutline = path.join(WORKDIR, `${team.slug}_left_paint_outline.png`);
  const rightPaintOutline = path.join(WORKDIR, `${team.slug}_right_paint_outline.png`);
  const withLeftOutline = path.join(WORKDIR, `${team.slug}_with_left_outline.jpg`);
  const withPaintOutlines = path.join(WORKDIR, `${team.slug}_with_paint_outlines.jpg`);
  const withLinework = path.join(WORKDIR, `${team.slug}_with_linework.jpg`);
  const withBasketOverlays = path.join(WORKDIR, `${team.slug}_with_basket_overlays.jpg`);
  const output = path.join(teamDir, `${team.slug}_court.jpg`);

  run(["-size", `${CANVAS.w}x${CANVAS.h}`, `xc:${oobColor}`, base]);
  drawWoodBase({ base, outsideWood, insideWood, outfile: withWood });
  applyMaskedColor({ base: withWood, mask: LEFT_PAINT_MASK, color: halfCircleColor, outfile: withHalfLeft });
  applyMaskedColor({ base: withHalfLeft, mask: RIGHT_PAINT_MASK, color: halfCircleColor, outfile: withBothHalf });
  drawLaneRects({ base: withBothHalf, color: laneColor, outfile: withLanes });

  run([
    LEFT_PAINT_MASK,
    "-alpha", "extract",
    "-threshold", "1%",
    "-morphology", "EdgeOut", "Diamond",
    leftPaintOutline,
  ]);
  run([
    RIGHT_PAINT_MASK,
    "-alpha", "extract",
    "-threshold", "1%",
    "-morphology", "EdgeOut", "Diamond",
    rightPaintOutline,
  ]);
  applyMaskedColor({ base: withLanes, mask: leftPaintOutline, color: COLORS.line, outfile: withLeftOutline });
  applyMaskedColor({ base: withLeftOutline, mask: rightPaintOutline, color: COLORS.line, outfile: withPaintOutlines });

  drawCourtLinework({ base: withPaintOutlines, outfile: withLinework });

  if (existsSync(LEFT_BASKET_ALPHA) && existsSync(RIGHT_BASKET_ALPHA)) {
    const args = [
      withLinework,
      LEFT_BASKET_ALPHA, "-geometry", "+126+922", "-compose", "over", "-composite",
      RIGHT_BASKET_ALPHA, "-geometry", "+3042+922", "-compose", "over", "-composite",
    ];
    if (existsSync(LEFT_BACKBOARD_OVERLAY) && existsSync(RIGHT_BACKBOARD_OVERLAY)) {
      args.push(
        LEFT_BACKBOARD_OVERLAY, "-geometry", "+132+994", "-compose", "over", "-composite",
        RIGHT_BACKBOARD_OVERLAY, "-geometry", "+3051+994", "-compose", "over", "-composite",
      );
    }
    if (existsSync(LEFT_RIMNET_OVERLAY) && existsSync(RIGHT_RIMNET_OVERLAY)) {
      args.push(
        LEFT_RIMNET_OVERLAY, "-geometry", "+190+930", "-compose", "over", "-composite",
        RIGHT_RIMNET_OVERLAY, "-geometry", "+2923+930", "-compose", "over", "-composite",
      );
    }
    args.push("-quality", "92", output);
    run(args);
  } else {
    run([
      withLinework,
      "-stroke", COLORS.support,
      "-strokewidth", "10",
      "-draw", `line 118,${RIM_LEFT.y} 72,${RIM_LEFT.y}`,
      "-draw", `line 3215,${RIM_RIGHT.y} 3261,${RIM_RIGHT.y}`,
      "-fill", "none",
      "-stroke", COLORS.backboardOuter,
      "-strokewidth", "10",
      "-draw", `rectangle 92,895 124,1189`,
      "-draw", `rectangle 3209,895 3241,1189`,
      "-stroke", COLORS.backboardInner,
      "-strokewidth", "6",
      "-draw", `rectangle 102,971 116,1113`,
      "-draw", `rectangle 3219,971 3233,1113`,
      "-fill", "none",
      "-stroke", COLORS.rim,
      "-strokewidth", "8",
      "-draw", `circle ${RIM_LEFT.x},${RIM_LEFT.y} ${RIM_LEFT.x + 46},${RIM_LEFT.y}`,
      "-draw", `circle ${RIM_RIGHT.x},${RIM_RIGHT.y} ${RIM_RIGHT.x + 46},${RIM_RIGHT.y}`,
      "-quality", "92",
      output,
    ]);
  }

  return {
    slug: team.slug,
    hardwood_variant: hardwoodKey,
    inside_tone: hardwood.inside,
    outside_tone: hardwood.outside,
    lane_fill: laneKey,
    half_circle_fill: halfCircleKey,
    oob_fill: oobKey,
    output,
  };
}

function main() {
  ensureDir(TMP_DIR);
  ensureDir(WORKDIR);
  const force = process.argv.includes("--force");
  const teamFilter = getArgValue("--team");

  const teams = parseTeams();
  const existing = existingCourtSlugs();
  const eligible = teams.filter((team) => {
    if (team.slug === "general") return false;
    if (A1_REFERENCE_SLUGS.has(team.slug)) return false;
    return true;
  });

  const targets = eligible.filter((team) => {
    if (teamFilter && team.slug !== teamFilter) return false;
    if (force) return true;
    return !existing.has(team.slug);
  });

  const hardwoodAssignments = assignBuckets(eligible, Object.fromEntries(Object.entries(HARDWOOD_VARIANTS).map(([k, v]) => [k, v.pct])), "hardwood");
  const laneAssignments = assignBuckets(eligible, LANE_DISTRIBUTION, "lane");
  const halfCircleAssignments = assignBuckets(eligible, HALF_CIRCLE_DISTRIBUTION, "half-circle");
  const oobAssignments = assignBuckets(eligible, OOB_DISTRIBUTION, "oob");

  const report = targets
    .sort((a, b) => a.slug.localeCompare(b.slug))
    .map((team) =>
      renderTeamCourt({
        team,
        hardwoodKey: hardwoodAssignments.get(team.slug),
        laneKey: laneAssignments.get(team.slug),
        halfCircleKey: halfCircleAssignments.get(team.slug),
        oobKey: oobAssignments.get(team.slug),
      })
    );

  writeFileSync(ASSIGNMENT_REPORT, JSON.stringify({ generated_count: report.length, assignments: report }, null, 2));
  process.stdout.write(`${report.length} courts generated\n${ASSIGNMENT_REPORT}\n`);
}

main();
