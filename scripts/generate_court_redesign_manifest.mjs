#!/usr/bin/env node

import { createHash, randomBytes } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const TEAMS_FILE = path.join(ROOT, "teams/128_teams.txt");
const OUTPUT_FILE = path.join(ROOT, "_documentation_master/projects/court_redesign_manifest.json");

const APPROVED = new Set([
  "abilene",
  "biloxi",
  "chapel_hill",
  "ida",
  "north_columbus",
  "templeton_wesley",
]);

const CONFERENCE_1 = new Set([
  "bentley_truman",
  "ocean_city",
  "lancaster",
  "four_corners",
  "morristown",
  "xavien",
  "little_york",
  "south_lancaster",
]);

const CENTER_COURT = [["none", 10], ["team_logo", 60], ["team_wordmark", 30]];
const NON_CENTER = [
  ["none", 50],
  ["deep_wing_2", 10],
  ["deep_wing_4", 5],
  ["inside_3pt_arc_2", 25],
  ["inside_3pt_arc_4", 10],
];
const HARDWOOD = [
  ["classic", 15],
  ["gloss", 40],
  ["fine_plank", 25],
  ["alternating_board", 15],
  ["parquet", 5],
];
const WING_WORDMARK_TYPES = ["school_name", "mascot_name"];
const WING_POSITIONS = ["upper_left", "lower_left", "upper_right", "lower_right"];

function slugify(value) {
  return String(value || "").trim().toLowerCase().replace(/['.]/g, "").replace(/-/g, " ").replace(/\s+/g, "_");
}

function getArg(flag) {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : null;
}

function parseTeams() {
  const rawLines = readFileSync(TEAMS_FILE, "utf8").split(/\r?\n/);
  const cutoff = rawLines.findIndex((line) => line.trim() === "prestige_rankings");
  const lines = (cutoff === -1 ? rawLines : rawLines.slice(0, cutoff)).filter((line) => line.trim());
  const headers = lines[0].split("\t");
  return lines.slice(1).map((line) => {
    const columns = line.split("\t");
    const team = Object.fromEntries(headers.map((header, index) => [header, columns[index] ?? ""]));
    return { ...team, slug: slugify(team.team) };
  });
}

function seededRandom(seed) {
  let counter = 0;
  return () => {
    const digest = createHash("sha256").update(`${seed}:${counter++}`).digest();
    return digest.readUInt32BE(0) / 0x100000000;
  };
}

function weightedRoll(random, options) {
  const roll = random() * options.reduce((sum, [, weight]) => sum + weight, 0);
  let cursor = 0;
  for (const [value, weight] of options) {
    cursor += weight;
    if (roll < cursor) return value;
  }
  return options.at(-1)[0];
}

function shuffled(items, random) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
  }
  return result;
}

function counts(rows, field) {
  return rows.reduce((result, row) => {
    result[row[field]] = (result[row[field]] || 0) + 1;
    return result;
  }, {});
}

const seed = getArg("--seed") || randomBytes(16).toString("hex");
const random = seededRandom(seed);
const allTeams = parseTeams();
const remaining = allTeams.filter((team) => !CONFERENCE_1.has(team.slug) && !APPROVED.has(team.slug));
const wingWordmarkTeams = new Set(shuffled(remaining, random).slice(0, 20).map((team) => team.slug));

const assignments = remaining.map((team) => ({
  team: team.team,
  slug: team.slug,
  mascot: team.mascot,
  conference: Number(team.conference),
  center_court: weightedRoll(random, CENTER_COURT),
  non_center_logos: weightedRoll(random, NON_CENTER),
  hardwood: weightedRoll(random, HARDWOOD),
  deep_wing_wordmark: wingWordmarkTeams.has(team.slug) ? {
    text_source: WING_WORDMARK_TYPES[Math.floor(random() * WING_WORDMARK_TYPES.length)],
    position: WING_POSITIONS[Math.floor(random() * WING_POSITIONS.length)],
  } : null,
})).sort((a, b) => a.slug.localeCompare(b.slug));

const manifest = {
  schema_version: 1,
  generated_at: new Date().toISOString(),
  seed,
  rules: {
    selection_method: "independent weighted roll per team; percentages are not final quotas",
    center_court_weights: Object.fromEntries(CENTER_COURT),
    non_center_logo_weights: Object.fromEntries(NON_CENTER),
    hardwood_weights: Object.fromEntries(HARDWOOD),
    deep_wing_wordmark_count: 20,
    deep_wing_wordmark_note: "Twenty additional teams beyond Conference-1 reference Ocean City",
  },
  excluded: {
    conference_1_count: allTeams.filter((team) => CONFERENCE_1.has(team.slug)).length,
    approved_non_conference_1: [...APPROVED].sort(),
  },
  assignment_count: assignments.length,
  realized_counts: {
    center_court: counts(assignments, "center_court"),
    non_center_logos: counts(assignments, "non_center_logos"),
    hardwood: counts(assignments, "hardwood"),
    deep_wing_wordmarks: assignments.filter((row) => row.deep_wing_wordmark).length,
  },
  assignments,
};

writeFileSync(OUTPUT_FILE, `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${OUTPUT_FILE}\nseed=${seed}\nassignments=${assignments.length}\n`);
