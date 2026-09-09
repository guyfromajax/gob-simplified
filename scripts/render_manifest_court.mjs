#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const IMAGE_ROOT = path.join(ROOT, "FrontEnd/static/images/teams");
const MANIFEST = JSON.parse(readFileSync(path.join(ROOT, "_documentation_master/projects/court_redesign_manifest.json"), "utf8"));
const CANVAS = "3333x2083";

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function overlay(asset, geometry, rotate = 0) {
  const transform = ["(", asset, "-resize", geometry.size];
  if (rotate) transform.push("-rotate", String(rotate));
  transform.push(")", "-gravity", geometry.gravity || "northwest", "-geometry", geometry.position, "-compose", "over", "-composite");
  return transform;
}

function pixelRgb(image, x, y) {
  const value = execFileSync("magick", [image, "-format", `%[pixel:p{${x},${y}}]`, "info:"], { encoding: "utf8" });
  const match = value.match(/(?:s?rgb)a?\((\d+)[, ]+(\d+)[, ]+(\d+)/i);
  return match ? match.slice(1, 4).map(Number) : null;
}

function colorDistance(a, b) {
  if (!a || !b) return Infinity;
  return Math.sqrt(a.reduce((sum, channel, index) => sum + ((channel - b[index]) ** 2), 0));
}

function paintMaskDecisions(base) {
  // Sample clear hardwood away from the center line and all painted geometry.
  const insideWood = pixelRgb(base, 1500, 1042);
  const outsideWood = pixelRgb(base, 1500, 500);
  const resemblesWood = (sample) => Math.min(colorDistance(sample, insideWood), colorDistance(sample, outsideWood)) < 42;
  return {
    excludeLanes: !resemblesWood(pixelRgb(base, 500, 1042)),
    excludeHalfCircles: !resemblesWood(pixelRgb(base, 980, 1042)),
  };
}

function hardwoodOverlay(kind, base) {
  if (kind === "classic") return [];
  if (kind === "gloss") {
    return [
      "(", "-size", "834x521", "xc:none", "-fill", "rgba(255,248,224,0.060)",
      "-draw", "ellipse 416,260 330,78 0,360", "-blur", "0x18", "-resize", `${CANVAS}!`, ")", "-compose", "screen", "-composite",
    ];
  }
  if (kind === "fine_plank") {
    return [
      "(", "-size", CANVAS, "xc:none", "-stroke", "rgba(91,55,31,0.065)", "-strokewidth", "2",
      "-draw", Array.from({ length: 22 }, (_, index) => `line 150,${200 + index * 78} 3183,${200 + index * 78}`).join(" "),
      "-stroke", "rgba(255,255,255,0.030)", "-strokewidth", "1",
      "-draw", Array.from({ length: 21 }, (_, index) => `line 150,${239 + index * 78} 3183,${239 + index * 78}`).join(" "),
      ")", "-compose", "over", "-composite",
    ];
  }
  if (kind === "alternating_board") {
    return [
      "(", "-size", CANVAS, "xc:none", "-fill", "rgba(108,67,35,0.050)",
      "-draw", Array.from({ length: 22 }, (_, index) => {
        const y = 180 + index * 78;
        return `rectangle 150,${y} 3183,${y + 38}`;
      }).join(" "),
      "-stroke", "rgba(84,48,26,0.095)", "-strokewidth", "2",
      "-draw", Array.from({ length: 23 }, (_, row) => {
        const y = 180 + row * 78;
        const offset = row % 2 ? 145 : 0;
        return Array.from({ length: 11 }, (_, column) => {
          const x = 300 + offset + column * 290;
          return `line ${x},${y} ${x},${Math.min(y + 78, 1924)}`;
        }).join(" ");
      }).join(" "), ")", "-compose", "over", "-composite",
    ];
  }
  if (kind === "parquet") {
    const { excludeLanes, excludeHalfCircles } = paintMaskDecisions(base);
    const result = [
      "(", "-size", CANVAS, "xc:none", "-fill", "rgba(83,46,24,0.085)",
      "-draw", Array.from({ length: 12 }, (_, row) => Array.from({ length: 16 }, (_, column) => {
        if ((row + column) % 2) return "";
        const x = 150 + column * 190;
        const y = 158 + row * 147;
        return `rectangle ${x},${y} ${Math.min(x + 190, 3183)},${Math.min(y + 147, 1924)}`;
      }).filter(Boolean).join(" ")).join(" "),
      "-fill", "rgba(255,238,203,0.045)",
      "-draw", Array.from({ length: 12 }, (_, row) => Array.from({ length: 16 }, (_, column) => {
        if ((row + column) % 2 === 0) return "";
        const x = 150 + column * 190;
        const y = 158 + row * 147;
        return `rectangle ${x},${y} ${Math.min(x + 190, 3183)},${Math.min(y + 147, 1924)}`;
      }).filter(Boolean).join(" ")).join(" "),
      "-stroke", "rgba(70,39,21,0.105)", "-strokewidth", "2",
      "-draw", Array.from({ length: 17 }, (_, index) => `line ${150 + index * 190},158 ${150 + index * 190},1924`).join(" "),
      "-draw", Array.from({ length: 13 }, (_, index) => `line 150,${158 + index * 147} 3183,${158 + index * 147}`).join(" "),
    ];
    if (excludeLanes || excludeHalfCircles) {
      result.push("(", "-size", CANVAS, "xc:black", "-fill", "white", "-stroke", "none", "-draw", "rectangle 150,158 3183,1924");
      if (excludeLanes) result.push("-fill", "black", "-draw", "rectangle 150,806 872,1271 rectangle 2452,806 3183,1271");
      if (excludeHalfCircles) result.push("-fill", "black", "-draw", "ellipse 872,1038.5 231,230.5 270,90 ellipse 2452,1038.5 231,230.5 90,270");
      result.push("-alpha", "copy", ")", "-compose", "DstIn", "-composite");
    }
    result.push(")", "-compose", "over", "-composite");
    return result;
  }
  fail(`Unknown hardwood: ${kind}`);
}

function reflectionOverlay(slug, hardwood, force = false) {
  if (!force && !["gloss", "alternating_board", "parquet"].includes(hardwood)) return [];
  let hash = 0;
  for (const char of slug) hash = ((hash * 31) + char.charCodeAt(0)) >>> 0;
  const ellipses = Array.from({ length: 8 }, (_, index) => {
    const x = Math.round((410 + index * 360 + ((hash >>> (index % 16)) % 13) - 6) / 4);
    const y = Math.round((1580 + ((hash >>> ((index + 5) % 16)) % 11) - 5) / 4);
    const rx = Math.round((65 + ((hash >>> ((index + 9) % 16)) % 8)) / 4);
    const ry = Math.round((86 + ((hash >>> ((index + 12) % 16)) % 10)) / 4);
    return `ellipse ${x},${y} ${rx},${ry} 0,360`;
  });
  return [
    "(", "-size", "834x521", "xc:none", "-fill", "rgba(255,248,220,0.42)",
    "-draw", ellipses.join(" "), "-blur", "0x6", "-resize", `${CANVAS}!`, ")", "-compose", "screen", "-composite",
  ];
}

function fixedBasketOverlays() {
  const leftBasket = path.join(ROOT, "tmp/court-template/bt_left_basket_alpha3.png");
  const rightBasket = path.join(ROOT, "tmp/court-template/bt_right_basket_alpha3.png");
  const leftRimNet = path.join(ROOT, "tmp/court-template/bt_left_rimnet_overlay.png");
  const rightRimNet = path.join(ROOT, "tmp/court-template/bt_right_rimnet_overlay.png");
  for (const asset of [leftBasket, rightBasket, leftRimNet, rightRimNet]) {
    if (!existsSync(asset)) fail(`Missing fixed basket overlay: ${asset}`);
  }
  return [
    "-gravity", "northwest",
    leftBasket, "-geometry", "+126+922", "-compose", "over", "-composite",
    rightBasket, "-geometry", "+3042+922", "-compose", "over", "-composite",
    leftRimNet, "-geometry", "+190+930", "-compose", "over", "-composite",
    rightRimNet, "-geometry", "+2923+930", "-compose", "over", "-composite",
  ];
}

const slug = arg("--team");
if (!slug || !/^[a-z0-9_]+$/.test(slug)) fail("Usage: node scripts/render_manifest_court.mjs --team <slug> --base <jpg> --out <jpg> [--force]");
const assignment = MANIFEST.assignments.find((entry) => entry.slug === slug);
if (!assignment) fail(`No manifest assignment for ${slug}`);

const teamDir = path.join(IMAGE_ROOT, slug);
const base = path.resolve(arg("--base", path.join(teamDir, `${slug}_court.jpg`)));
const out = path.resolve(arg("--out", path.join(teamDir, `${slug}_court_redesign_preview.jpg`)));
const logo = path.join(teamDir, `${slug}_logo_primary.png`);
const wordmark = path.join(teamDir, `${slug}_wordmark.png`);
const schoolName = path.join(teamDir, `${slug}_team_name.png`);
const wingWordmarks = assignment.deep_wing_wordmarks || (assignment.deep_wing_wordmark ? [assignment.deep_wing_wordmark] : []);
if (!existsSync(base)) fail(`Missing base: ${base}`);
if (existsSync(out) && !process.argv.includes("--force")) fail(`Refusing to overwrite ${out}; pass --force`);
if ((assignment.center_court === "team_logo" || assignment.non_center_logos !== "none") && !existsSync(logo)) fail(`Missing logo: ${logo}`);
if ((assignment.center_court === "team_wordmark" || wingWordmarks.some((entry) => entry.text_source === "mascot_name")) && !existsSync(wordmark)) fail(`Missing wordmark: ${wordmark}`);
if (wingWordmarks.some((entry) => entry.text_source === "school_name") && !existsSync(schoolName)) fail(`Missing school name: ${schoolName}`);

const args = [base, ...hardwoodOverlay(assignment.hardwood, base), ...reflectionOverlay(slug, assignment.hardwood, assignment.force_reflections)];

const centerOffset = assignment.center_offset || { x: 0, y: 0 };
const centerGeometry = `${centerOffset.x >= 0 ? "+" : ""}${centerOffset.x}${centerOffset.y >= 0 ? "+" : ""}${centerOffset.y}`;
if (assignment.center_court === "team_logo") args.push(...overlay(logo, { size: "560x560", position: centerGeometry, gravity: "center" }));
if (assignment.center_court === "team_wordmark") args.push(...overlay(wordmark, { size: "760x360", position: centerGeometry, gravity: "center" }));

const deepWing = {
  upper_left: { size: "330x300", position: "+1190+350", rotate: 0 },
  lower_left: { size: "330x300", position: "+1190+1430", rotate: 180 },
  upper_right: { size: "330x300", position: "+1815+350", rotate: 0 },
  lower_right: { size: "330x300", position: "+1815+1430", rotate: 180 },
};
const insideArc = {
  upper_left: { size: "250x250", position: "+320+430", rotate: 0 },
  lower_left: { size: "250x250", position: "+320+1403", rotate: 180 },
  upper_right: { size: "250x250", position: "+2763+430", rotate: 0 },
  lower_right: { size: "250x250", position: "+2763+1403", rotate: 180 },
};

const treatment = assignment.non_center_logos;
if (treatment === "deep_wing_2") {
  for (const key of ["upper_left", "lower_right"]) args.push(...overlay(logo, deepWing[key], deepWing[key].rotate));
} else if (treatment === "deep_wing_4") {
  for (const key of Object.keys(deepWing)) args.push(...overlay(logo, deepWing[key], deepWing[key].rotate));
} else if (treatment === "deep_wing_4_and_inside_3pt_arc_4") {
  for (const key of Object.keys(deepWing)) args.push(...overlay(logo, deepWing[key], deepWing[key].rotate));
  for (const key of Object.keys(insideArc)) args.push(...overlay(logo, insideArc[key], insideArc[key].rotate));
} else if (treatment === "inside_3pt_arc_2") {
  for (const key of ["upper_left", "lower_right"]) args.push(...overlay(logo, insideArc[key], insideArc[key].rotate));
} else if (treatment === "inside_3pt_arc_4") {
  for (const key of Object.keys(insideArc)) args.push(...overlay(logo, insideArc[key], insideArc[key].rotate));
} else if (treatment !== "none") fail(`Unknown non-center treatment: ${treatment}`);

for (const wingMark of wingWordmarks) {
  const mark = wingMark.text_source === "school_name" ? schoolName : wordmark;
  const wordmarkPositions = {
    upper_left: { x: 1075, y: 390 }, lower_left: { x: 1075, y: 1530 },
    upper_right: { x: 1700, y: 390 }, lower_right: { x: 1700, y: 1530 },
  };
  const anchor = wordmarkPositions[wingMark.position];
  if (!anchor) fail(`Unknown deep-wing wordmark position: ${wingMark.position}`);
  const scale = wingMark.scale || 1;
  const x = anchor.x + (wingMark.offset_x || 0);
  const y = anchor.y + (wingMark.offset_y || 0);
  args.push(...overlay(mark, {
    size: `${Math.round(560 * scale)}x${Math.round(130 * scale)}`,
    position: `${x >= 0 ? "+" : ""}${x}${y >= 0 ? "+" : ""}${y}`,
  }, wingMark.rotate || 0));
}

// Basket geometry is animation-critical. Keep these legacy assets and pixel
// anchors as the final court layer; never scale or infer their placement.
args.push(...fixedBasketOverlays());
args.push("-quality", "92", out);
execFileSync("magick", args, { stdio: "inherit" });
const dimensions = execFileSync("magick", ["identify", "-format", "%wx%h", out], { encoding: "utf8" });
if (dimensions !== CANVAS) fail(`Unexpected dimensions for ${slug}: ${dimensions}`);
process.stdout.write(`${slug}: ${out} (${dimensions})\n`);
