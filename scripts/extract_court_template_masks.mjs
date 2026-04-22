#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SOURCE = path.join(
  ROOT,
  "FrontEnd/static/images/teams/bentley_truman/bentley_truman_court.jpg",
);
const OUTDIR = path.join(ROOT, "tmp/court-template");

const CANVAS = { width: 3333, height: 2083 };

const REGION_BOXES = {
  border_left: { x1: 0, y1: 0, x2: 190, y2: 2083 },
  border_right: { x1: 3143, y1: 0, x2: 3333, y2: 2083 },
  center_logo: { x1: 1325, y1: 689, x2: 2006, y2: 1348 },
  left_upper_secondary: { x1: 420, y1: 245, x2: 980, y2: 760 },
  left_lower_secondary: { x1: 430, y1: 1325, x2: 985, y2: 1835 },
  right_upper_secondary: { x1: 2348, y1: 245, x2: 2908, y2: 760 },
  right_lower_secondary: { x1: 2348, y1: 1325, x2: 2908, y2: 1835 },
  center_wordmark: { x1: 350, y1: 620, x2: 2980, y2: 1520 },
  right_of_center_wordmark: { x1: 1650, y1: 725, x2: 2625, y2: 1460 },
  left_paint: { x1: 150, y1: 672, x2: 1085, y2: 1411 },
  right_paint: { x1: 2248, y1: 672, x2: 3183, y2: 1411 },
  center_circle_zone: { x1: 1140, y1: 515, x2: 2193, y2: 1568 },
  midcourt_neutral_strip: { x1: 1075, y1: 420, x2: 2258, y2: 1663 },
  left_basket_overlay: { x1: 0, y1: 620, x2: 360, y2: 1470 },
  right_basket_overlay: { x1: 2973, y1: 620, x2: 3333, y2: 1470 },
};

const RUNTIME_ANCHORS = {
  away_rim: { x: 300, y: 1042 },
  home_rim: { x: 3033, y: 1042 },
  away_top_key: { x: 1200, y: 1042 },
  home_top_key: { x: 2133, y: 1042 },
  clamp_bounds_px: { left: 167, right: 3166, top: 83, bottom: 2041 },
};

function runMagick(args) {
  execFileSync("magick", args, { stdio: "pipe" });
}

function ensureDir(dir) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

function drawRectanglesMask(outfile, boxes) {
  const args = [
    "-size",
    `${CANVAS.width}x${CANVAS.height}`,
    "xc:black",
    "-fill",
    "white",
  ];

  for (const box of boxes) {
    args.push(
      "-draw",
      `rectangle ${box.x1},${box.y1} ${box.x2 - 1},${box.y2 - 1}`,
    );
  }

  args.push(outfile);
  runMagick(args);
}

function compositeCropMask({
  source,
  crop,
  color,
  fuzz = "18%",
  outfile,
  offset,
}) {
  const [x1, y1, x2, y2] = crop;
  const width = x2 - x1;
  const height = y2 - y1;
  const tempCrop = path.join(OUTDIR, `${path.basename(outfile, ".png")}_crop.png`);
  const tempMask = path.join(OUTDIR, `${path.basename(outfile, ".png")}_localmask.png`);

  runMagick([source, "-crop", `${width}x${height}+${x1}+${y1}`, "+repage", tempCrop]);
  runMagick([
    tempCrop,
    "-alpha",
    "off",
    "-fuzz",
    fuzz,
    "-fill",
    "white",
    "+opaque",
    color,
    "-fill",
    "black",
    "+opaque",
    "white",
    "-negate",
    tempMask,
  ]);
  runMagick([
    "-size",
    `${CANVAS.width}x${CANVAS.height}`,
    "xc:black",
    tempMask,
    "-geometry",
    `+${offset.x}+${offset.y}`,
    "-compose",
    "screen",
    "-composite",
    outfile,
  ]);
}

function drawGuideOverlay(outfile) {
  const args = [SOURCE];

  const guideColors = {
    center_logo: "#00d1ff",
    secondary: "#ffd166",
    wordmark: "#ef476f",
    paint: "#06d6a0",
    border: "#ffffff",
    geometry: "#8d99ae",
  };

  const drawBox = (box, color) => {
    args.push(
      "-stroke",
      color,
      "-strokewidth",
      "8",
      "-fill",
      "none",
      "-draw",
      `rectangle ${box.x1},${box.y1} ${box.x2 - 1},${box.y2 - 1}`,
    );
  };

  drawBox(REGION_BOXES.center_logo, guideColors.center_logo);
  drawBox(REGION_BOXES.left_upper_secondary, guideColors.secondary);
  drawBox(REGION_BOXES.left_lower_secondary, guideColors.secondary);
  drawBox(REGION_BOXES.right_upper_secondary, guideColors.secondary);
  drawBox(REGION_BOXES.right_lower_secondary, guideColors.secondary);
  drawBox(REGION_BOXES.center_wordmark, guideColors.wordmark);
  drawBox(REGION_BOXES.right_of_center_wordmark, guideColors.wordmark);
  drawBox(REGION_BOXES.left_paint, guideColors.paint);
  drawBox(REGION_BOXES.right_paint, guideColors.paint);
  drawBox(REGION_BOXES.center_circle_zone, guideColors.geometry);
  drawBox(REGION_BOXES.left_basket_overlay, "#ff9f1c");
  drawBox(REGION_BOXES.right_basket_overlay, "#ff9f1c");
  drawBox(REGION_BOXES.border_left, guideColors.border);
  drawBox(REGION_BOXES.border_right, guideColors.border);

  for (const point of Object.values(RUNTIME_ANCHORS)) {
    if (!("x" in point) || !("y" in point)) continue;
    args.push(
      "-stroke",
      "#ff006e",
      "-strokewidth",
      "8",
      "-draw",
      `circle ${point.x},${point.y} ${point.x + 18},${point.y}`,
    );
  }

  args.push(outfile);
  runMagick(args);
}

function cropAsset({ source, box, outfile }) {
  runMagick([
    source,
    "-crop",
    `${box.x2 - box.x1}x${box.y2 - box.y1}+${box.x1}+${box.y1}`,
    "+repage",
    outfile,
  ]);
}

function main() {
  ensureDir(OUTDIR);

  copyFileSync(SOURCE, path.join(OUTDIR, "master_reference_bentley_truman_court.jpg"));

  const metadata = {
    source_asset: "FrontEnd/static/images/teams/bentley_truman/bentley_truman_court.jpg",
    canvas: CANVAS,
    runtime_anchors: RUNTIME_ANCHORS,
    regions: REGION_BOXES,
    notes: [
      "Mask artifacts are Bentley-Truman-derived first-pass extraction assets.",
      "Border and placement-slot masks are deterministic rectangle masks.",
      "Paint masks are color-extracted from bounded crops to avoid center-logo contamination.",
      "Hardwood split masks are not extracted yet; they need a more deliberate shape pass.",
    ],
  };

  writeFileSync(
    path.join(OUTDIR, "court_template_regions.json"),
    `${JSON.stringify(metadata, null, 2)}\n`,
    "utf8",
  );

  drawRectanglesMask(path.join(OUTDIR, "mask_border_bands.png"), [
    REGION_BOXES.border_left,
    REGION_BOXES.border_right,
  ]);

  drawRectanglesMask(path.join(OUTDIR, "mask_center_logo_slot.png"), [
    REGION_BOXES.center_logo,
  ]);

  drawRectanglesMask(path.join(OUTDIR, "mask_secondary_slots.png"), [
    REGION_BOXES.left_upper_secondary,
    REGION_BOXES.left_lower_secondary,
    REGION_BOXES.right_upper_secondary,
    REGION_BOXES.right_lower_secondary,
  ]);

  drawRectanglesMask(path.join(OUTDIR, "mask_wordmark_slots.png"), [
    REGION_BOXES.center_wordmark,
    REGION_BOXES.right_of_center_wordmark,
  ]);

  cropAsset({
    source: SOURCE,
    box: REGION_BOXES.left_basket_overlay,
    outfile: path.join(OUTDIR, "left_basket_overlay_crop.png"),
  });

  cropAsset({
    source: SOURCE,
    box: REGION_BOXES.right_basket_overlay,
    outfile: path.join(OUTDIR, "right_basket_overlay_crop.png"),
  });

  compositeCropMask({
    source: SOURCE,
    crop: [
      REGION_BOXES.left_paint.x1,
      REGION_BOXES.left_paint.y1,
      REGION_BOXES.left_paint.x2,
      REGION_BOXES.left_paint.y2,
    ],
    color: "srgb(60,102,176)",
    outfile: path.join(OUTDIR, "mask_left_paint.png"),
    offset: { x: REGION_BOXES.left_paint.x1, y: REGION_BOXES.left_paint.y1 },
  });

  compositeCropMask({
    source: SOURCE,
    crop: [
      REGION_BOXES.right_paint.x1,
      REGION_BOXES.right_paint.y1,
      REGION_BOXES.right_paint.x2,
      REGION_BOXES.right_paint.y2,
    ],
    color: "srgb(60,102,176)",
    outfile: path.join(OUTDIR, "mask_right_paint.png"),
    offset: { x: REGION_BOXES.right_paint.x1, y: REGION_BOXES.right_paint.y1 },
  });

  drawGuideOverlay(path.join(OUTDIR, "court_template_guide_overlay.png"));

  process.stdout.write(`Extracted court template artifacts to ${OUTDIR}\n`);
}

main();
