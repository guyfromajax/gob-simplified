#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const IMAGE_ROOT = path.join(ROOT, "FrontEnd/static/images/teams");
const CANVAS = "3333x2083";

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function run(args) {
  execFileSync("magick", args, { stdio: "inherit" });
}

const slug = arg("--team");
if (!slug || !/^[a-z0-9_]+$/.test(slug)) {
  fail("Usage: node scripts/apply_branded_court_template.mjs --team <slug> [--layout <name>] [--base <jpg>] [--logo <png>] [--out <jpg>] [--force]");
}

const teamDir = path.join(IMAGE_ROOT, slug);
const base = path.resolve(arg("--base", path.join(teamDir, `${slug}_court.jpg`)));
const logo = path.resolve(arg("--logo", path.join(teamDir, `${slug}_logo_primary.png`)));
const wordmark = path.resolve(arg("--wordmark", path.join(teamDir, `${slug}_wordmark.png`)));
const baselineLeft = path.join(teamDir, "identity_test", `${slug}_baseline_left.png`);
const baselineRight = path.join(teamDir, "identity_test", `${slug}_baseline_right.png`);
const out = path.resolve(arg("--out", path.join(teamDir, `${slug}_court_branded_preview.jpg`)));
const layout = arg("--layout", "center_mark");

const requiredAssets = layout === "center_wordmark_reflections"
  ? [base, wordmark]
  : layout === "center_ship_alternating_baselines"
    ? [base, logo, baselineLeft, baselineRight]
    : [base, logo];
for (const required of requiredAssets) {
  if (!existsSync(required)) fail(`Missing required asset: ${required}`);
}
if (existsSync(out) && !process.argv.includes("--force")) {
  fail(`Refusing to overwrite ${out}; pass --force to replace it.`);
}

const layouts = {
  center_mark: [
    "(", "-size", CANVAS, "xc:none",
    "-fill", "rgba(255,255,255,0.085)",
    "-draw", "ellipse 820,410 500,120 0,360",
    "-draw", "ellipse 2480,1610 590,135 0,360",
    "-fill", "rgba(255,244,214,0.055)",
    "-draw", "ellipse 1666,1042 980,170 0,360",
    "-blur", "0x42", ")", "-compose", "over", "-composite",
    "(", logo, "-resize", "560x560", ")",
    "-gravity", "center", "-compose", "over", "-composite",
  ],
  center_logo_planks: [
    // Narrow-board seams and staggered joins. All strokes stay within the
    // playable-floor rectangle and never replace the fixed court geometry.
    "(", "-size", CANVAS, "xc:none",
    "-stroke", "rgba(92,58,32,0.060)", "-strokewidth", "2",
    "-draw", Array.from({ length: 21 }, (_, i) => 220 + i * 82).flatMap((y) =>
      y >= 806 && y <= 1271
        ? [`line 1103,${y} 2221,${y}`]
        : [`line 150,${y} 3183,${y}`]
    ).join(" "),
    "-stroke", "rgba(255,255,255,0.030)", "-strokewidth", "1",
    "-draw", Array.from({ length: 20 }, (_, i) => 260 + i * 82).flatMap((y) =>
      y >= 806 && y <= 1271
        ? [`line 1103,${y} 2221,${y}`]
        : [`line 150,${y} 3183,${y}`]
    ).join(" "),
    ")", "-compose", "over", "-composite",
    // Parallel overhead fixtures create a visibly different reflection family.
    "(", "-size", CANVAS, "xc:none", "-fill", "rgba(255,255,255,0.160)",
    "-draw", "roundrectangle 430,350 1160,415 32,32",
    "-draw", "roundrectangle 1295,350 2025,415 32,32",
    "-draw", "roundrectangle 2160,350 2890,415 32,32",
    "-draw", "roundrectangle 430,1665 1160,1730 32,32",
    "-draw", "roundrectangle 1295,1665 2025,1730 32,32",
    "-draw", "roundrectangle 2160,1665 2890,1730 32,32",
    "-blur", "0x18", ")", "-compose", "screen", "-composite",
    "(", logo, "-resize", "560x560", ")",
    "-gravity", "center", "-compose", "over", "-composite",
  ],
  center_wordmark_reflections: [
    // Bright, soft-edged overhead fixture blooms modeled after the established
    // Conference 1 courts, which place the visible reflection row on the lower half.
    "(", "-size", CANVAS, "xc:none",
    "-fill", "rgba(255,255,255,0.46)",
    "-draw", "ellipse 407,1577 70,93 0,360",
    "-draw", "ellipse 768,1582 65,87 0,360",
    "-fill", "rgba(255,255,255,0.43)",
    "-draw", "ellipse 1138,1579 71,96 0,360",
    "-draw", "ellipse 1497,1584 67,89 0,360",
    "-fill", "rgba(255,255,255,0.45)",
    "-draw", "ellipse 1835,1578 69,93 0,360",
    "-draw", "ellipse 2192,1581 66,86 0,360",
    "-fill", "rgba(255,255,255,0.44)",
    "-draw", "ellipse 2564,1576 72,95 0,360",
    "-draw", "ellipse 2923,1583 67,91 0,360",
    "-blur", "0x24", ")", "-compose", "screen", "-composite",
    "(", wordmark, "-resize", "760x360", ")",
    "-gravity", "center", "-compose", "over", "-composite",
  ],
  center_ship_alternating_baselines: [
    // Restrained alternating-board tones with staggered joins.
    "(", "-size", CANVAS, "xc:none",
    "-fill", "rgba(118,70,35,0.045)",
    "-draw", Array.from({ length: 22 }, (_, i) => {
      const y1 = 180 + i * 78;
      return `rectangle 150,${y1} 3183,${y1 + 38}`;
    }).join(" "),
    "-stroke", "rgba(93,52,27,0.105)", "-strokewidth", "2",
    "-draw", Array.from({ length: 23 }, (_, row) => {
      const y = 180 + row * 78;
      const offset = row % 2 === 0 ? 0 : 145;
      return Array.from({ length: 11 }, (_, col) => {
        const x = 300 + offset + col * 290;
        return `line ${x},${y} ${x},${Math.min(y + 78, 1900)}`;
      }).join(" ");
    }).join(" "),
    ")", "-compose", "over", "-composite",
    // One Conference 1-style reflection row with barely perceptible variation.
    "(", "-size", CANVAS, "xc:none",
    "-fill", "rgba(255,248,218,0.44)",
    "-draw", "ellipse 406,1578 69,91 0,360",
    "-draw", "ellipse 767,1582 65,86 0,360",
    "-fill", "rgba(255,248,218,0.41)",
    "-draw", "ellipse 1137,1579 72,94 0,360",
    "-draw", "ellipse 1496,1584 66,88 0,360",
    "-fill", "rgba(255,248,218,0.43)",
    "-draw", "ellipse 1836,1577 70,92 0,360",
    "-draw", "ellipse 2191,1581 65,85 0,360",
    "-fill", "rgba(255,248,218,0.42)",
    "-draw", "ellipse 2563,1576 71,95 0,360",
    "-draw", "ellipse 2924,1583 67,89 0,360",
    "-blur", "0x24", ")", "-compose", "screen", "-composite",
    "(", logo, "-resize", "510x610", ")",
    "-gravity", "center", "-compose", "over", "-composite",
    // Mirrored baseline names, each facing inward from its own side.
    baselineLeft,
    "-gravity", "northwest", "-geometry", "+84+800", "-compose", "over", "-composite",
    baselineRight,
    "-gravity", "northwest", "-geometry", "+3192+800", "-compose", "over", "-composite",
  ],
  badge_mirrors: [
    // Broad, diffused arena gloss with no hard fixture edges.
    "(", "-size", CANVAS, "xc:none",
    "-fill", "rgba(255,255,255,0.115)",
    "-draw", "ellipse 780,430 650,170 0,360",
    "-draw", "ellipse 2550,1650 720,190 0,360",
    "-fill", "rgba(214,230,255,0.070)",
    "-draw", "ellipse 1666,1042 1120,230 0,360",
    "-blur", "0x58", ")", "-compose", "screen", "-composite",
    "(", logo, "-resize", "500x600", ")",
    "-gravity", "center", "-compose", "over", "-composite",
    "(", logo, "-resize", "235x275", ")",
    "-gravity", "northwest", "-geometry", "+320+430", "-compose", "over", "-composite",
    "(", logo, "-resize", "235x275", "-rotate", "180", ")",
    "-gravity", "southwest", "-geometry", "+320+430", "-compose", "over", "-composite",
    "(", logo, "-resize", "235x275", ")",
    "-gravity", "northeast", "-geometry", "+320+430", "-compose", "over", "-composite",
    "(", logo, "-resize", "235x275", "-rotate", "180", ")",
    "-gravity", "southeast", "-geometry", "+320+430", "-compose", "over", "-composite",
  ],
};

if (!layouts[layout]) fail(`Unknown layout: ${layout}`);
if (layout === "badge_mirrors" && slug !== "ida") {
  fail("badge_mirrors repeats the primary logo and is reserved for the approved IDA exception");
}
if (layout === "center_ship_alternating_baselines" && slug !== "templeton_wesley") {
  fail("center_ship_alternating_baselines is reserved for Templeton-Wesley");
}

// Gameplay geometry is inherited unchanged from the supplied court; every
// template operation below is a decorative overlay.
run([
  base,
  ...layouts[layout],
  "-quality", "92", out,
]);

const dimensions = execFileSync("magick", ["identify", "-format", "%wx%h", out], { encoding: "utf8" });
if (dimensions !== CANVAS) fail(`Unexpected output dimensions: ${dimensions}`);
process.stdout.write(`Rendered ${out} (${dimensions})\n`);
