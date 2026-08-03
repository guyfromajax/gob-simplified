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
const OOB_LINE_BOUNDS = { x1: 150, y1: 84, x2: 3183, y2: 1998 };
const TOP_HORIZONTAL_OOB_Y = 158;
const BOTTOM_HORIZONTAL_OOB_Y = 1924;
const FLOOR_EDGE_TOP_Y = 208;
const FLOOR_EDGE_BOTTOM_Y = 1878;
const THREE_POINT_LEFT = {
  startX: 96,
  controlX: 1112,
  topY: 308,
  bottomY: 1770,
};
const THREE_POINT_RIGHT = {
  startX: 3237,
  controlX: 2213,
  topY: 308,
  bottomY: 1770,
};
const THREE_POINT_LINE_LEFT = {
  startX: OOB_LINE_BOUNDS.x1,
  controlX: THREE_POINT_LEFT.controlX,
  topY: THREE_POINT_LEFT.topY,
  bottomY: THREE_POINT_LEFT.bottomY,
};
const THREE_POINT_LINE_RIGHT = {
  startX: OOB_LINE_BOUNDS.x2,
  controlX: THREE_POINT_RIGHT.controlX,
  topY: THREE_POINT_RIGHT.topY,
  bottomY: THREE_POINT_RIGHT.bottomY,
};
const FREE_THROW_LEFT_BBOX = { x1: 684, y1: 859, x2: 1044, y2: 1219, start: 248, end: 112 };
const FREE_THROW_RIGHT_BBOX = { x1: 2288, y1: 859, x2: 2648, y2: 1219, start: 68, end: 292 };
const CENTER = { x: 1666, y: 1042 };
const LANE_LEFT_RECT = { x1: 150, y1: 806, x2: 872, y2: 1271 };
const LANE_RIGHT_RECT = { x1: 2452, y1: 806, x2: 3183, y2: 1271 };
const LEFT_HALF_CIRCLE = { x1: 641, y1: 808, x2: 1103, y2: 1269 };
const RIGHT_HALF_CIRCLE = { x1: 2221, y1: 808, x2: 2683, y2: 1269 };
const RIM_LEFT = { x: 300, y: 1042 };
const RIM_RIGHT = { x: 3033, y: 1042 };
const LANE_OUTSIDE_HASHES_LEFT_X = [458, 558, 658, 758];
const LANE_OUTSIDE_HASHES_RIGHT_X = [2575, 2675, 2775, 2875];
const LANE_OUTSIDE_HASH_TOP = { y1: 782, y2: LANE_LEFT_RECT.y1 };
const LANE_OUTSIDE_HASH_BOTTOM = { y1: LANE_LEFT_RECT.y2, y2: 1296 };

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
  primary: 70,
  secondary: 20,
  inside_hardwood: 10,
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

const LINE_DISTRIBUTION = {
  dark_grey: 25,
  black: 25,
  white: 25,
  primary: 25,
};

const TEAM_LINE_OVERRIDES = {
  abilene: "black",
  grupenberg: "black",
  queens_guard: "white",
  southwest_miner: "black",
  upstate: "black",
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
  backboardGlass: "rgba(82,95,122,0.45)",
};

const LEFT_BACKBOARD_EXT = {
  outer: { x1: 166, y1: 882, x2: 196, y2: 1212 },
  glass: { x1: 172, y1: 888, x2: 190, y2: 1206 },
};

const RIGHT_BACKBOARD_EXT = {
  outer: { x1: 3137, y1: 882, x2: 3167, y2: 1212 },
  glass: { x1: 3143, y1: 888, x2: 3161, y2: 1206 },
};

const ABILENE_FLOOR = {
  maple: "#D8B180",
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
  const leftPath = `M ${OOB_LINE_BOUNDS.x1},${THREE_POINT_LINE_LEFT.topY} Q ${THREE_POINT_LINE_LEFT.controlX},${THREE_POINT_LINE_LEFT.topY} ${THREE_POINT_LINE_LEFT.controlX},1042 Q ${THREE_POINT_LINE_LEFT.controlX},${THREE_POINT_LINE_LEFT.bottomY} ${OOB_LINE_BOUNDS.x1},${THREE_POINT_LINE_LEFT.bottomY} L ${OOB_LINE_BOUNDS.x1},${THREE_POINT_LINE_LEFT.topY} Z`;
  const rightPath = `M ${OOB_LINE_BOUNDS.x2},${THREE_POINT_LINE_RIGHT.topY} Q ${THREE_POINT_LINE_RIGHT.controlX},${THREE_POINT_LINE_RIGHT.topY} ${THREE_POINT_LINE_RIGHT.controlX},1042 Q ${THREE_POINT_LINE_RIGHT.controlX},${THREE_POINT_LINE_RIGHT.bottomY} ${OOB_LINE_BOUNDS.x2},${THREE_POINT_LINE_RIGHT.bottomY} L ${OOB_LINE_BOUNDS.x2},${THREE_POINT_LINE_RIGHT.topY} Z`;
  run([
    base,
    "-fill", outsideWood,
    "-stroke", "none",
    "-draw", `rectangle ${OOB_LINE_BOUNDS.x1},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${BOTTOM_HORIZONTAL_OOB_Y}`,
    "-fill", insideWood,
    "-draw", `path '${leftPath}'`,
    "-draw", `path '${rightPath}'`,
    outfile,
  ]);
}

function drawHardwoodFinish({ base, outfile, stem }) {
  const grainOverlay = path.join(WORKDIR, `${stem}_hardwood_grain.png`);
  const grainDraws = [];
  const shortGrainDraws = [];
  const plankBands = [];
  const fullWidthStartX = OOB_LINE_BOUNDS.x1 + 22;
  const fullWidthEndX = OOB_LINE_BOUNDS.x2 - 22;

  for (let i = 0; i < 34; i += 1) {
    const bandTop = TOP_HORIZONTAL_OOB_Y + 12 + (i * 52);
    const bandBottom = Math.min(bandTop + 28 + ((i % 4) * 6), BOTTOM_HORIZONTAL_OOB_Y - 10);
    const fill = i % 2 === 0 ? "rgba(255,248,238,0.055)" : "rgba(140,101,66,0.042)";
    plankBands.push("-draw", `fill ${fill} stroke none rectangle ${OOB_LINE_BOUNDS.x1},${bandTop} ${OOB_LINE_BOUNDS.x2},${bandBottom}`);
  }

  for (let i = 0; i < 26; i += 1) {
    const y = TOP_HORIZONTAL_OOB_Y + 38 + (i * 68);
    const c1 = CENTER.x - 520 + ((i % 5) * 28);
    const c2 = CENTER.x + 520 - ((i % 4) * 34);
    const y1 = y + ((i % 3) - 1) * 12;
    const y2 = y + ((i % 4) - 1.5) * 10;
    const stroke = i % 3 === 0 ? "rgba(255,248,237,0.18)" : "rgba(145,104,68,0.12)";
    const width = i % 5 === 0 ? 5 : 3;
    grainDraws.push("-stroke", stroke);
    grainDraws.push("-strokewidth", String(width));
    grainDraws.push("-draw", `path 'M ${fullWidthStartX},${y} Q ${c1},${y1} ${CENTER.x},${y + 6} Q ${c2},${y2} ${fullWidthEndX},${y + ((i % 2) * 6 - 3)}'`);
  }

  for (let i = 0; i < 42; i += 1) {
    const startX = OOB_LINE_BOUNDS.x1 + 140 + ((i * 101) % 2350);
    const endX = Math.min(startX + 210 + ((i % 6) * 38), OOB_LINE_BOUNDS.x2 - 120);
    const y = TOP_HORIZONTAL_OOB_Y + 34 + ((i * 57) % (BOTTOM_HORIZONTAL_OOB_Y - TOP_HORIZONTAL_OOB_Y - 80));
    const c = startX + ((endX - startX) / 2);
    const bend = ((i % 5) - 2) * 10;
    const stroke = i % 2 === 0 ? "rgba(255,246,233,0.12)" : "rgba(146,106,68,0.09)";
    shortGrainDraws.push("-stroke", stroke);
    shortGrainDraws.push("-strokewidth", i % 4 === 0 ? "3" : "2");
    shortGrainDraws.push("-draw", `path 'M ${startX},${y} Q ${c},${y + bend} ${endX},${y + ((i % 3) - 1) * 5}'`);
  }

  run([
    "-size", `${CANVAS.w}x${CANVAS.h}`,
    "xc:none",
    "-fill", "none",
    ...plankBands,
    ...grainDraws,
    ...shortGrainDraws,
    "-blur", "0x0.8",
    grainOverlay,
  ]);

  run([
    base,
    grainOverlay, "-compose", "Over", "-composite",
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

function compositeLaneHardwood({ base, source, outfile, stem }) {
  const mask = path.join(WORKDIR, `${stem}_lane_hardwood_mask.png`);
  const masked = path.join(WORKDIR, `${stem}_lane_hardwood_masked.png`);
  run([
    "-size", `${CANVAS.w}x${CANVAS.h}`,
    "xc:black",
    "-fill", "white",
    "-stroke", "none",
    "-draw", `rectangle ${LANE_LEFT_RECT.x1},${LANE_LEFT_RECT.y1} ${LANE_LEFT_RECT.x2},${LANE_LEFT_RECT.y2}`,
    "-draw", `rectangle ${LANE_RIGHT_RECT.x1},${LANE_RIGHT_RECT.y1} ${LANE_RIGHT_RECT.x2},${LANE_RIGHT_RECT.y2}`,
    mask,
  ]);
  run([
    source,
    mask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    masked,
  ]);
  run([
    base,
    masked,
    "-compose", "Over",
    "-composite",
    outfile,
  ]);
}

function drawHalfCircleCaps({ base, color, outfile }) {
  run([
    base,
    "-fill", color,
    "-stroke", "none",
    "-draw", `ellipse ${(LEFT_HALF_CIRCLE.x1 + LEFT_HALF_CIRCLE.x2) / 2},${(LEFT_HALF_CIRCLE.y1 + LEFT_HALF_CIRCLE.y2) / 2} ${(LEFT_HALF_CIRCLE.x2 - LEFT_HALF_CIRCLE.x1) / 2},${(LEFT_HALF_CIRCLE.y2 - LEFT_HALF_CIRCLE.y1) / 2} 270,90`,
    "-draw", `ellipse ${(RIGHT_HALF_CIRCLE.x1 + RIGHT_HALF_CIRCLE.x2) / 2},${(RIGHT_HALF_CIRCLE.y1 + RIGHT_HALF_CIRCLE.y2) / 2} ${(RIGHT_HALF_CIRCLE.x2 - RIGHT_HALF_CIRCLE.x1) / 2},${(RIGHT_HALF_CIRCLE.y2 - RIGHT_HALF_CIRCLE.y1) / 2} 90,270`,
    outfile,
  ]);
}

function compositeHalfCircleHardwood({ base, source, outfile, stem }) {
  const mask = path.join(WORKDIR, `${stem}_halfcircle_hardwood_mask.png`);
  const masked = path.join(WORKDIR, `${stem}_halfcircle_hardwood_masked.png`);
  run([
    "-size", `${CANVAS.w}x${CANVAS.h}`,
    "xc:black",
    "-fill", "white",
    "-stroke", "none",
    "-draw", `ellipse ${(LEFT_HALF_CIRCLE.x1 + LEFT_HALF_CIRCLE.x2) / 2},${(LEFT_HALF_CIRCLE.y1 + LEFT_HALF_CIRCLE.y2) / 2} ${(LEFT_HALF_CIRCLE.x2 - LEFT_HALF_CIRCLE.x1) / 2},${(LEFT_HALF_CIRCLE.y2 - LEFT_HALF_CIRCLE.y1) / 2} 270,90`,
    "-draw", `ellipse ${(RIGHT_HALF_CIRCLE.x1 + RIGHT_HALF_CIRCLE.x2) / 2},${(RIGHT_HALF_CIRCLE.y1 + RIGHT_HALF_CIRCLE.y2) / 2} ${(RIGHT_HALF_CIRCLE.x2 - RIGHT_HALF_CIRCLE.x1) / 2},${(RIGHT_HALF_CIRCLE.y2 - RIGHT_HALF_CIRCLE.y1) / 2} 90,270`,
    mask,
  ]);
  run([
    source,
    mask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    masked,
  ]);
  run([
    base,
    masked,
    "-compose", "Over",
    "-composite",
    outfile,
  ]);
}

function drawPaintLinework({ base, lineColor, outfile }) {
  run([
    base,
    "-fill", "none",
    "-stroke", lineColor,
    "-strokewidth", "8",
    "-draw", `rectangle ${LANE_LEFT_RECT.x1},${LANE_LEFT_RECT.y1} ${LANE_LEFT_RECT.x2},${LANE_LEFT_RECT.y2}`,
    "-draw", `rectangle ${LANE_RIGHT_RECT.x1},${LANE_RIGHT_RECT.y1} ${LANE_RIGHT_RECT.x2},${LANE_RIGHT_RECT.y2}`,
    "-draw", `arc ${LEFT_HALF_CIRCLE.x1},${LEFT_HALF_CIRCLE.y1} ${LEFT_HALF_CIRCLE.x2},${LEFT_HALF_CIRCLE.y2} 270,90`,
    "-draw", `arc ${RIGHT_HALF_CIRCLE.x1},${RIGHT_HALF_CIRCLE.y1} ${RIGHT_HALF_CIRCLE.x2},${RIGHT_HALF_CIRCLE.y2} 90,270`,
    "-draw", `stroke-dasharray 40,62 stroke-dashoffset 20 arc ${LEFT_HALF_CIRCLE.x1},${LEFT_HALF_CIRCLE.y1} ${LEFT_HALF_CIRCLE.x2},${LEFT_HALF_CIRCLE.y2} 90,270`,
    "-draw", `stroke-dasharray 40,62 stroke-dashoffset 20 arc ${RIGHT_HALF_CIRCLE.x1},${RIGHT_HALF_CIRCLE.y1} ${RIGHT_HALF_CIRCLE.x2},${RIGHT_HALF_CIRCLE.y2} 270,90`,
    outfile,
  ]);
}

function drawCourtLinework({ base, lineColor, outfile }) {
  run([
    base,
    "-fill", "none",
    "-stroke", lineColor,
    "-strokewidth", "8",
    "-draw", `line ${OOB_LINE_BOUNDS.x1},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${TOP_HORIZONTAL_OOB_Y}`,
    "-draw", `line ${OOB_LINE_BOUNDS.x1},${BOTTOM_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${BOTTOM_HORIZONTAL_OOB_Y}`,
    "-draw", `line ${OOB_LINE_BOUNDS.x1},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x1},${BOTTOM_HORIZONTAL_OOB_Y}`,
    "-draw", `line ${OOB_LINE_BOUNDS.x2},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${BOTTOM_HORIZONTAL_OOB_Y}`,
    "-draw", `line ${CENTER.x},${TOP_HORIZONTAL_OOB_Y} ${CENTER.x},${BOTTOM_HORIZONTAL_OOB_Y}`,
    "-draw", `path 'M ${THREE_POINT_LINE_LEFT.startX},${THREE_POINT_LINE_LEFT.topY} Q ${THREE_POINT_LINE_LEFT.controlX},${THREE_POINT_LINE_LEFT.topY} ${THREE_POINT_LINE_LEFT.controlX},1042 Q ${THREE_POINT_LINE_LEFT.controlX},${THREE_POINT_LINE_LEFT.bottomY} ${THREE_POINT_LINE_LEFT.startX},${THREE_POINT_LINE_LEFT.bottomY}'`,
    "-draw", `path 'M ${THREE_POINT_LINE_RIGHT.startX},${THREE_POINT_LINE_RIGHT.topY} Q ${THREE_POINT_LINE_RIGHT.controlX},${THREE_POINT_LINE_RIGHT.topY} ${THREE_POINT_LINE_RIGHT.controlX},1042 Q ${THREE_POINT_LINE_RIGHT.controlX},${THREE_POINT_LINE_RIGHT.bottomY} ${THREE_POINT_LINE_RIGHT.startX},${THREE_POINT_LINE_RIGHT.bottomY}'`,
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

function drawBackboardHeightExtensions({ base, outfile }) {
  run([
    base,
    "-fill", COLORS.backboardOuter,
    "-stroke", "none",
    "-draw", `rectangle ${LEFT_BACKBOARD_EXT.outer.x1},${LEFT_BACKBOARD_EXT.outer.y1} ${LEFT_BACKBOARD_EXT.outer.x2},${LEFT_BACKBOARD_EXT.outer.y2}`,
    "-draw", `rectangle ${RIGHT_BACKBOARD_EXT.outer.x1},${RIGHT_BACKBOARD_EXT.outer.y1} ${RIGHT_BACKBOARD_EXT.outer.x2},${RIGHT_BACKBOARD_EXT.outer.y2}`,
    "-fill", COLORS.backboardGlass,
    "-draw", `rectangle ${LEFT_BACKBOARD_EXT.glass.x1},${LEFT_BACKBOARD_EXT.glass.y1} ${LEFT_BACKBOARD_EXT.glass.x2},${LEFT_BACKBOARD_EXT.glass.y2}`,
    "-draw", `rectangle ${RIGHT_BACKBOARD_EXT.glass.x1},${RIGHT_BACKBOARD_EXT.glass.y1} ${RIGHT_BACKBOARD_EXT.glass.x2},${RIGHT_BACKBOARD_EXT.glass.y2}`,
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
    case "white":
      return "#F4F3EF";
    case "dark_grey":
      return COLORS.line;
    default:
      throw new Error(`Unknown color token: ${token}`);
  }
}

function resolveLineToken({ assignedToken, laneKey, halfCircleKey }) {
  if (assignedToken !== "primary") return assignedToken;
  if (laneKey === "primary" || halfCircleKey === "primary") {
    if (laneKey === "secondary" || halfCircleKey === "secondary") {
      return "dark_grey";
    }
    return "secondary";
  }
  return "primary";
}

function renderTeamCourt({
  team,
  hardwoodKey,
  laneKey,
  halfCircleKey,
  oobKey,
  lineKey,
  outputOverride = null,
  workStem = null,
  disableAbileneMapleOverride = false,
  disableOverlays = false,
}) {
  const teamDir = path.join(TEAM_IMAGE_DIR, team.slug);
  if (!outputOverride) ensureDir(teamDir);
  ensureDir(WORKDIR);

  const hardwood = HARDWOOD_VARIANTS[hardwoodKey];
  let insideWood = HARDWOOD_TONES[hardwood.inside];
  let outsideWood = HARDWOOD_TONES[hardwood.outside];
  const primary = hex(team.primary_color, "#2a2a2a");
  const secondary = hex(team.secondary_color, "#f2f2f2");
  if (team.slug === "abilene" && !disableAbileneMapleOverride) {
    insideWood = ABILENE_FLOOR.maple;
    outsideWood = ABILENE_FLOOR.maple;
  }
  const laneColor = team.slug === "abilene"
    ? primary
    : resolveAssignmentColor({ token: laneKey, primary, secondary, insideWood, outsideWood });
  const effectiveHalfCircleKey = team.slug === "abilene" ? "primary" : halfCircleKey;
  const halfCircleColor = resolveAssignmentColor({ token: effectiveHalfCircleKey, primary, secondary, insideWood, outsideWood });
  const oobColor = resolveAssignmentColor({ token: oobKey, primary, secondary, insideWood, outsideWood });
  const effectiveLineToken = resolveLineToken({
    assignedToken: TEAM_LINE_OVERRIDES[team.slug] || lineKey,
    laneKey,
    halfCircleKey: effectiveHalfCircleKey,
  });
  const lineColor = resolveAssignmentColor({
    token: effectiveLineToken,
    primary,
    secondary,
    insideWood,
    outsideWood,
  });

  const stem = workStem || team.slug;
  const base = path.join(WORKDIR, `${stem}_base.jpg`);
  const withWood = path.join(WORKDIR, `${stem}_with_wood.jpg`);
  const withHardwoodFinish = path.join(WORKDIR, `${stem}_with_hardwood_finish.jpg`);
  const withHalfCaps = path.join(WORKDIR, `${stem}_with_half_caps.jpg`);
  const withHalfCapsHardwood = path.join(WORKDIR, `${stem}_with_half_caps_hardwood.jpg`);
  const withLanes = path.join(WORKDIR, `${stem}_with_lanes.jpg`);
  const withLanesHardwood = path.join(WORKDIR, `${stem}_with_lanes_hardwood.jpg`);
  const withPaintOutlines = path.join(WORKDIR, `${stem}_with_paint_outlines.jpg`);
  const withLinework = path.join(WORKDIR, `${stem}_with_linework.jpg`);
  const withBoardExtensions = path.join(WORKDIR, `${stem}_with_board_extensions.jpg`);
  const output = outputOverride || path.join(teamDir, `${team.slug}_court.jpg`);

  run(["-size", `${CANVAS.w}x${CANVAS.h}`, `xc:${oobColor}`, base]);
  drawWoodBase({ base, outsideWood, insideWood, outfile: withWood });
  drawHardwoodFinish({ base: withWood, outfile: withHardwoodFinish, stem });
  drawHalfCircleCaps({ base: withHardwoodFinish, color: halfCircleColor, outfile: withHalfCaps });
  const halfCapsBase = halfCircleKey === "inside_hardwood"
    ? (compositeHalfCircleHardwood({ base: withHalfCaps, source: withHardwoodFinish, outfile: withHalfCapsHardwood, stem }), withHalfCapsHardwood)
    : withHalfCaps;
  drawLaneRects({ base: halfCapsBase, color: laneColor, outfile: withLanes });
  const lanesBase = laneKey === "inside_hardwood"
    ? (compositeLaneHardwood({ base: withLanes, source: withHardwoodFinish, outfile: withLanesHardwood, stem }), withLanesHardwood)
    : withLanes;
  drawPaintLinework({ base: lanesBase, lineColor, outfile: withPaintOutlines });

  drawCourtLinework({ base: withPaintOutlines, lineColor, outfile: withLinework });
  drawBackboardHeightExtensions({ base: withLinework, outfile: withBoardExtensions });

  if (
    !disableOverlays &&
    existsSync(LEFT_BASKET_ALPHA) &&
    existsSync(RIGHT_BASKET_ALPHA)
  ) {
    const args = [
      withBoardExtensions,
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
    // Fallback rim/board strokes (no PNG overlays). Start from withBoardExtensions
    // so height extensions match the port's useOverlays:false path.
    const fallbackArgs = [
      withBoardExtensions,
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
    ];
    if (String(output).toLowerCase().endsWith(".png")) {
      fallbackArgs.push(output);
    } else {
      fallbackArgs.push("-quality", "92", output);
    }
    run(fallbackArgs);
  }

  return {
    slug: team.slug,
    hardwood_variant: hardwoodKey,
    inside_tone: hardwood.inside,
    outside_tone: hardwood.outside,
    lane_fill: laneKey,
    half_circle_fill: halfCircleKey,
    oob_fill: oobKey,
    line_fill: effectiveLineToken,
    output,
    resolved: {
      primary,
      secondary,
      inside_wood: insideWood,
      outside_wood: outsideWood,
      lane_color: laneColor,
      half_circle_color: halfCircleColor,
      oob_color: oobColor,
      line_color: lineColor,
    },
  };
}

/**
 * Fixture render for port↔oracle sweeps. Uses a synthetic team so tokens resolve
 * against the supplied primary/secondary; overlays disabled for fair compare.
 */
function renderOracleFixture({
  hardwoodKey,
  laneKey = "primary",
  halfCircleKey = "secondary",
  oobKey = "black",
  lineKey = "dark_grey",
  primary = "#27408E",
  secondary = "#FF00FF",
  outPath,
}) {
  if (!HARDWOOD_VARIANTS[hardwoodKey]) {
    throw new Error(`Unknown hardwoodKey: ${hardwoodKey}`);
  }
  const team = {
    slug: "oracle_fixture",
    primary_color: primary,
    secondary_color: secondary,
  };
  return renderTeamCourt({
    team,
    hardwoodKey,
    laneKey,
    halfCircleKey,
    oobKey,
    lineKey,
    outputOverride: outPath,
    workStem: `oracle_${hardwoodKey}_${laneKey}_${halfCircleKey}_${oobKey}`,
    disableAbileneMapleOverride: true,
    disableOverlays: true,
  });
}

function main() {
  ensureDir(TMP_DIR);
  ensureDir(WORKDIR);
  const force = process.argv.includes("--force");
  const teamFilter = getArgValue("--team");
  const renderTemplateVariants = process.argv.includes("--render-template-variants");
  const oracleRender = process.argv.includes("--oracle-render");

  if (oracleRender) {
    const hardwoodKey = getArgValue("--hardwood");
    const outPath = getArgValue("--out");
    if (!hardwoodKey || !outPath) {
      throw new Error("--oracle-render requires --hardwood <key> and --out <path>");
    }
    const report = renderOracleFixture({
      hardwoodKey,
      laneKey: getArgValue("--lane") || "primary",
      halfCircleKey: getArgValue("--half") || "secondary",
      oobKey: getArgValue("--oob") || "black",
      lineKey: getArgValue("--line") || "dark_grey",
      primary: getArgValue("--primary") || "#27408E",
      secondary: getArgValue("--secondary") || "#FF00FF",
      outPath,
    });
    process.stdout.write(JSON.stringify(report) + "\n");
    return;
  }

  if (renderTemplateVariants) {
    const abilene = parseTeams().find((team) => team.slug === "abilene");
    const previewVariants = Object.keys(HARDWOOD_VARIANTS).filter((key) => key !== "medium_medium");
    const report = previewVariants.map((hardwoodKey) =>
      renderTeamCourt({
        team: abilene,
        hardwoodKey,
        laneKey: "primary",
        halfCircleKey: "primary",
        oobKey: "outside_hardwood",
        lineKey: "dark_grey",
        outputOverride: path.join(TMP_DIR, `abilene_template_${hardwoodKey}.jpg`),
        workStem: `abilene_template_${hardwoodKey}`,
        disableAbileneMapleOverride: true,
      })
    );
    process.stdout.write(`${report.length} template variants generated\n`);
    return;
  }

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
  const lineAssignments = assignBuckets(eligible, LINE_DISTRIBUTION, "line");

  const report = targets
    .sort((a, b) => a.slug.localeCompare(b.slug))
    .map((team) =>
      renderTeamCourt({
        team,
        hardwoodKey: hardwoodAssignments.get(team.slug),
        laneKey: laneAssignments.get(team.slug),
        halfCircleKey: halfCircleAssignments.get(team.slug),
        oobKey: oobAssignments.get(team.slug),
        lineKey: lineAssignments.get(team.slug),
      })
    );

  writeFileSync(ASSIGNMENT_REPORT, JSON.stringify({ generated_count: report.length, assignments: report }, null, 2));
  process.stdout.write(`${report.length} courts generated\n${ASSIGNMENT_REPORT}\n`);
}

main();
