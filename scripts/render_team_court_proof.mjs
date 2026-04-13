#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const TEAMS_FILE = path.join(ROOT, "teams/128_teams.txt");
const TEMPLATE_DIR = path.join(ROOT, "tmp/court-template");
const MASTER_COURT = path.join(TEMPLATE_DIR, "master_clean_court_base.jpg");
const REGION_FILE = path.join(TEMPLATE_DIR, "court_template_regions.json");
const PROOF_DIR = path.join(TEMPLATE_DIR, "proofs");
const WORK_DIR = path.join(TEMPLATE_DIR, "work");
const TEAM_IMAGE_DIR = path.join(ROOT, "FrontEnd/static/images/teams");

function run(cmd, args) {
  execFileSync(cmd, args, { stdio: "pipe" });
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
  const lines = readFileSync(TEAMS_FILE, "utf8")
    .split(/\r?\n/)
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

function findTeam(teamArg) {
  const teams = parseTeams();
  const normalized = slugify(teamArg);
  const bySlug = teams.find((t) => t.slug === normalized);
  if (bySlug) return bySlug;
  const byName = teams.find((t) => t.team.toLowerCase() === String(teamArg).toLowerCase());
  if (byName) return byName;
  throw new Error(`Unknown team: ${teamArg}`);
}

function readRegions() {
  return JSON.parse(readFileSync(REGION_FILE, "utf8"));
}

function hex(value, fallback) {
  const v = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(v) ? v : fallback;
}

function initials(teamName, mascot) {
  const teamParts = (teamName || "").split(/[\s-]+/).filter(Boolean);
  const mascotParts = (mascot || "").split(/[\s-]+/).filter(Boolean);
  const a = teamParts[0]?.[0] || "T";
  const b = mascotParts[0]?.[0] || (teamParts[1]?.[0] || "");
  return `${a}${b}`.toUpperCase();
}

function safeWordmark(teamName) {
  return String(teamName || "")
    .replace(/['.]/g, "")
    .toUpperCase();
}

function makeBadge({ outfile, width, height, fill, stroke, text, textFill, pointsize }) {
  run("magick", [
    "-size", `${width}x${height}`,
    "xc:none",
    "-fill", fill,
    "-stroke", stroke,
    "-strokewidth", "16",
    "-draw", `roundrectangle 20,20 ${width - 21},${height - 21} 110,110`,
    "-fill", textFill,
    "-stroke", "none",
    "-font", "DejaVu-Sans-Bold",
    "-gravity", "center",
    "-pointsize", String(pointsize),
    "-annotate", "0", text,
    outfile,
  ]);
}

function makeVerticalWord({ outfile, text, width, height, fill, pointsize }) {
  const temp = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_temp.png`);
  run("magick", [
    "-size", `${height}x${width}`,
    "xc:none",
    "-fill", fill,
    "-stroke", "none",
    "-font", "DejaVu-Sans-Bold",
    "-gravity", "center",
    "-pointsize", String(pointsize),
    "-annotate", "0", text,
    temp,
  ]);
  run("magick", [temp, "-rotate", "-90", outfile]);
}

function makeTextChip({
  outfile,
  width,
  height,
  fill,
  stroke,
  text,
  textFill,
  pointsize,
  radius = 70,
  strokeWidth = 12,
}) {
  run("magick", [
    "-size", `${width}x${height}`,
    "xc:none",
    "-fill", fill,
    "-stroke", stroke,
    "-strokewidth", String(strokeWidth),
    "-draw", `roundrectangle 10,10 ${width - 11},${height - 11} ${radius},${radius}`,
    "-fill", textFill,
    "-stroke", "none",
    "-font", "DejaVu-Sans-Bold",
    "-gravity", "center",
    "-pointsize", String(pointsize),
    "-annotate", "0", text,
    outfile,
  ]);
}

function makeRoundedImagePlate({
  source,
  outfile,
  width,
  height,
  borderColor,
  borderWidth,
  radius,
  crop,
}) {
  const sourceFrame = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_source.png`);
  const mask = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_mask.png`);
  const borderMask = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_border_mask.png`);
  const borderShape = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_border_shape.png`);
  const innerW = width - borderWidth * 2;
  const innerH = height - borderWidth * 2;
  const innerRadius = Math.max(12, radius - borderWidth);

  run("magick", [
    source,
    "-gravity", crop.gravity ?? "west",
    "-crop", `${crop.width}x${crop.height}+${crop.x ?? 0}+${crop.y ?? 0}`,
    "+repage",
    "-resize", `${innerW}x${innerH}`,
    "-gravity", "center",
    "-background", "none",
    "-extent", `${innerW}x${innerH}`,
    sourceFrame,
  ]);

  run("magick", [
    "-size", `${innerW}x${innerH}`,
    "xc:none",
    "-fill", "white",
    "-stroke", "none",
    "-draw", `roundrectangle 0,0 ${innerW - 1},${innerH - 1} ${innerRadius},${innerRadius}`,
    mask,
  ]);

  run("magick", [
    sourceFrame,
    mask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    "PNG32:" + sourceFrame,
  ]);

  run("magick", [
    "-size", `${width}x${height}`,
    "xc:none",
    "-fill", "white",
    "-stroke", "none",
    "-draw", `roundrectangle 0,0 ${width - 1},${height - 1} ${radius},${radius}`,
    borderMask,
  ]);

  run("magick", [
    "-size", `${width}x${height}`,
    `xc:${borderColor}`,
    borderMask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    "PNG32:" + borderShape,
  ]);

  run("magick", [
    "-size", `${width}x${height}`,
    "xc:none",
    borderShape,
    "-compose", "Over",
    "-composite",
    sourceFrame,
    "-gravity", "center",
    "-geometry", `+0+0`,
    "-compose", "Over",
    "-composite",
    "-type", "TrueColorAlpha",
    "PNG32:" + outfile,
  ]);
}

function makeCutoutPlate({
  source,
  outfile,
  width,
  height,
  borderColor,
  borderWidth,
  radius,
  fillColor,
  crop,
  fuzz = "28%",
  subjectScale = 0.82,
}) {
  const cropped = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_cropped.png`);
  const cutout = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_cutout.png`);
  const trimmed = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_trimmed.png`);
  const fitted = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_fitted.png`);
  const plate = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_plate.png`);
  const innerPlate = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_inner_plate.png`);
  const innerMask = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_inner_mask.png`);
  const mask = path.join(WORK_DIR, `${path.basename(outfile, ".png")}_plate_mask.png`);
  const innerW = width - borderWidth * 2;
  const innerH = height - borderWidth * 2;
  const innerRadius = Math.max(12, radius - borderWidth);
  const subjectW = Math.round(innerW * subjectScale);
  const subjectH = Math.round(innerH * subjectScale);

  run("magick", [
    source,
    "-gravity", crop.gravity ?? "west",
    "-crop", `${crop.width}x${crop.height}+${crop.x ?? 0}+${crop.y ?? 0}`,
    "+repage",
    cropped,
  ]);

  const maxX = crop.width - 1;
  const maxY = crop.height - 1;
  run("magick", [
    cropped,
    "-alpha", "set",
    "-fuzz", fuzz,
    "-fill", "none",
    "-draw", `color 1,1 floodfill`,
    "-draw", `color 1,${maxY - 1} floodfill`,
    "-draw", `color ${maxX - 1},1 floodfill`,
    "-draw", `color ${maxX - 1},${maxY - 1} floodfill`,
    "-channel", "a",
    "-morphology", "Open", "Diamond:1",
    "+channel",
    "PNG32:" + cutout,
  ]);

  run("magick", [
    cutout,
    "-trim",
    "+repage",
    "PNG32:" + trimmed,
  ]);

  run("magick", [
    trimmed,
    "-resize", `${subjectW}x${subjectH}`,
    "-gravity", "center",
    "-background", "none",
    "-extent", `${innerW}x${innerH}`,
    "PNG32:" + fitted,
  ]);

  run("magick", [
    "-size", `${innerW}x${innerH}`,
    `xc:${fillColor}`,
    innerPlate,
  ]);

  run("magick", [
    "-size", `${innerW}x${innerH}`,
    "xc:none",
    "-fill", "white",
    "-stroke", "none",
    "-draw", `roundrectangle 0,0 ${innerW - 1},${innerH - 1} ${innerRadius},${innerRadius}`,
    innerMask,
  ]);

  run("magick", [
    innerPlate,
    innerMask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    "PNG32:" + innerPlate,
  ]);

  run("magick", [
    "-size", `${width}x${height}`,
    "xc:none",
    "-fill", "white",
    "-stroke", "none",
    "-draw", `roundrectangle 0,0 ${width - 1},${height - 1} ${radius},${radius}`,
    mask,
  ]);

  run("magick", [
    plate,
    mask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    "PNG32:" + plate,
  ]);

  run("magick", [
    plate,
    innerPlate,
    "-gravity", "center",
    "-compose", "Over",
    "-composite",
    fitted,
    "-gravity", "center",
    "-compose", "Over",
    "-composite",
    "PNG32:" + outfile,
  ]);
}

function applyMaskedColor({ base, mask, color, outfile }) {
  run("magick", [
    base,
    "(",
    "-size", "3333x2083",
    `xc:${color}`,
    mask,
    "-alpha", "off",
    "-compose", "CopyOpacity",
    "-composite",
    ")",
    "-compose", "Over",
    "-composite",
    outfile,
  ]);
}

function main() {
  const teamArgIndex = process.argv.indexOf("--team");
  if (teamArgIndex === -1 || !process.argv[teamArgIndex + 1]) {
    throw new Error("Usage: node scripts/render_team_court_proof.mjs --team <team_slug_or_name>");
  }

  ensureDir(PROOF_DIR);
  ensureDir(WORK_DIR);

  const team = findTeam(process.argv[teamArgIndex + 1]);
  const regions = readRegions().regions;
  const primary = hex(team.primary_color, "#2a2a2a");
  const secondary = hex(team.secondary_color, "#f2f2f2");
  const dark = "#111111";
  const white = "#ffffff";
  const markText = initials(team.team, team.mascot);
  const wordmark = safeWordmark(team.team);

  const output = path.join(PROOF_DIR, `${team.slug}_court_proof.jpg`);
  const stage1 = path.join(WORK_DIR, `${team.slug}_stage1.jpg`);
  const stage2 = path.join(WORK_DIR, `${team.slug}_stage2.jpg`);
  const stage3 = path.join(WORK_DIR, `${team.slug}_stage3.jpg`);
  const stage4 = path.join(WORK_DIR, `${team.slug}_stage4.jpg`);

  const centerBadge = path.join(WORK_DIR, `${team.slug}_center_badge.png`);
  const leftSecondaryChip = path.join(WORK_DIR, `${team.slug}_left_secondary_chip.png`);
  const rightSecondaryChip = path.join(WORK_DIR, `${team.slug}_right_secondary_chip.png`);
  const leftVertical = path.join(WORK_DIR, `${team.slug}_left_vertical.png`);
  const rightVertical = path.join(WORK_DIR, `${team.slug}_right_vertical.png`);
  const bannerPrimary = path.join(TEAM_IMAGE_DIR, team.slug, `${team.slug}_banner_primary.jpg`);

  if (existsSync(bannerPrimary)) {
    makeRoundedImagePlate({
      source: bannerPrimary,
      outfile: centerBadge,
      width: regions.center_logo.x2 - regions.center_logo.x1,
      height: regions.center_logo.y2 - regions.center_logo.y1,
      borderColor: white,
      borderWidth: 18,
      radius: 120,
      crop: { width: 520, height: 620, gravity: "west" },
    });

    makeTextChip({
      outfile: leftSecondaryChip,
      width: 420,
      height: 120,
      fill: dark,
      stroke: white,
      text: safeWordmark(team.team),
      textFill: secondary === "#ffffff" ? white : secondary,
      pointsize: 48,
      radius: 44,
      strokeWidth: 10,
    });

    makeTextChip({
      outfile: rightSecondaryChip,
      width: 360,
      height: 120,
      fill: dark,
      stroke: white,
      text: safeWordmark(team.mascot),
      textFill: secondary === "#ffffff" ? white : secondary,
      pointsize: 44,
      radius: 44,
      strokeWidth: 10,
    });
  } else {
    makeBadge({
      outfile: centerBadge,
      width: regions.center_logo.x2 - regions.center_logo.x1,
      height: regions.center_logo.y2 - regions.center_logo.y1,
      fill: primary,
      stroke: white,
      text: markText,
      textFill: secondary === "#ffffff" ? dark : secondary,
      pointsize: 240,
    });

    makeTextChip({
      outfile: leftSecondaryChip,
      width: 360,
      height: 120,
      fill: dark,
      stroke: white,
      text: markText,
      textFill: secondary === "#ffffff" ? white : secondary,
      pointsize: 70,
      radius: 44,
      strokeWidth: 10,
    });
    makeTextChip({
      outfile: rightSecondaryChip,
      width: 360,
      height: 120,
      fill: dark,
      stroke: white,
      text: safeWordmark(team.mascot),
      textFill: secondary === "#ffffff" ? white : secondary,
      pointsize: 44,
      radius: 44,
      strokeWidth: 10,
    });
  }

  makeVerticalWord({
    outfile: leftVertical,
    text: wordmark,
    width: 1700,
    height: 180,
    fill: white,
    pointsize: 110,
  });

  makeVerticalWord({
    outfile: rightVertical,
    text: wordmark,
    width: 1700,
    height: 180,
    fill: white,
    pointsize: 110,
  });

  applyMaskedColor({
    base: MASTER_COURT,
    mask: path.join(TEMPLATE_DIR, "mask_border_bands.png"),
    color: primary,
    outfile: stage1,
  });

  applyMaskedColor({
    base: stage1,
    mask: path.join(TEMPLATE_DIR, "mask_left_paint.png"),
    color: primary,
    outfile: stage2,
  });

  applyMaskedColor({
    base: stage2,
    mask: path.join(TEMPLATE_DIR, "mask_right_paint.png"),
    color: primary,
    outfile: stage3,
  });

  run("magick", [
    stage3,
    centerBadge, "-gravity", "NorthWest", "-geometry", `+${regions.center_logo.x1}+${regions.center_logo.y1}`, "-compose", "Over", "-composite",
    leftSecondaryChip, "-gravity", "NorthWest", "-geometry", `+${regions.left_upper_secondary.x1 + 70}+${regions.left_upper_secondary.y1 + 185}`, "-compose", "Over", "-composite",
    rightSecondaryChip, "-gravity", "NorthWest", "-geometry", `+${regions.right_upper_secondary.x1 + 105}+${regions.right_upper_secondary.y1 + 185}`, "-compose", "Over", "-composite",
    stage4,
  ]);

  run("magick", [
    stage4,
    leftVertical, "-gravity", "NorthWest", "-geometry", "+5+150", "-compose", "Over", "-composite",
    rightVertical, "-gravity", "NorthWest", "-geometry", "+3148+150", "-compose", "Over", "-composite",
    "-quality", "92",
    output,
  ]);

  process.stdout.write(`${team.slug}: ${output}\n`);
}

main();
