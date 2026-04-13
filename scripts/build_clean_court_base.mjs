#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const OUTDIR = path.join(ROOT, "tmp/court-template");
const WORKDIR = path.join(OUTDIR, "clean-base-work");
const LEFT_BASKET_ALPHA = path.join(OUTDIR, "bt_left_basket_alpha3.png");
const RIGHT_BASKET_ALPHA = path.join(OUTDIR, "bt_right_basket_alpha3.png");
const LEFT_PAINT_MASK = path.join(OUTDIR, "mask_left_paint.png");
const RIGHT_PAINT_MASK = path.join(OUTDIR, "mask_right_paint.png");

const CANVAS = { w: 3333, h: 2083 };
const FLOOR = { x1: 75, y1: 60, x2: 3258, y2: 2023 };
const BORDER_LEFT = { x1: 0, y1: 0, x2: 190, y2: 2083 };
const BORDER_RIGHT = { x1: 3143, y1: 0, x2: 3333, y2: 2083 };
const KEY_LEFT = { x1: 150, y1: 816, x2: 1085, y2: 1262 };
const KEY_RIGHT = { x1: 2248, y1: 816, x2: 3183, y2: 1262 };
const KEY_LEFT_ARC_CENTER = { x: 864, y: 1039, r: 223 };
const KEY_RIGHT_ARC_CENTER = { x: 2468, y: 1039, r: 223 };
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
const KEY_HASHES_LEFT_X = [398, 495, 594, 694];
const KEY_HASHES_RIGHT_X = [2639, 2738, 2837, 2936];
const KEY_HASH_TOP = { y1: 335, y2: 369 };
const KEY_HASH_BOTTOM = { y1: 831, y2: 864 };
const RIM_LEFT = { x: 300, y: 1042 };
const RIM_RIGHT = { x: 3033, y: 1042 };
const CENTER = { x: 1666, y: 1042 };
const FLOOR_LINE_TOP = 210;
const FLOOR_LINE_BOTTOM = 1874;

const COLORS = {
  border: "#050505",
  line: "#6e675f",
  paint: "#8d9096",
  wood: "#ecdbc9",
  rim: "#e35a4a",
  backboardOuter: "#d7dde8",
  backboardInner: "#f6f7fb",
  stanchion: "#2d2d2d",
  support: "#1b1b1b",
};

function run(args) {
  execFileSync("magick", args, { stdio: "pipe" });
}

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function applyMaskedColor({ base, mask, color, outfile }) {
  run([
    base,
    "(",
    "-size",
    `${CANVAS.w}x${CANVAS.h}`,
    `xc:${color}`,
    mask,
    "-alpha",
    "off",
    "-compose",
    "CopyOpacity",
    "-composite",
    ")",
    "-compose",
    "Over",
    "-composite",
    outfile,
  ]);
}

function main() {
  ensureDir(OUTDIR);
  ensureDir(WORKDIR);

  const base = path.join(WORKDIR, "base.jpg");
  const withFloor = path.join(WORKDIR, "with_floor.jpg");
  const withLeftPaint = path.join(WORKDIR, "with_left_paint.jpg");
  const withBothPaints = path.join(WORKDIR, "with_both_paints.jpg");
  const leftPaintOutline = path.join(WORKDIR, "left_paint_outline.png");
  const rightPaintOutline = path.join(WORKDIR, "right_paint_outline.png");
  const withLeftOutline = path.join(WORKDIR, "with_left_outline.jpg");
  const withPaintOutlines = path.join(WORKDIR, "with_paint_outlines.jpg");
  const output = path.join(OUTDIR, "master_clean_court_base.jpg");

  run([
    "-size",
    `${CANVAS.w}x${CANVAS.h}`,
    `xc:${COLORS.border}`,
    base,
  ]);

  run([
    base,
    "(",
    "-size",
    `${FLOOR.x2 - FLOOR.x1}x${FLOOR.y2 - FLOOR.y1}`,
    `xc:${COLORS.wood}`,
    ")",
    "-geometry",
    `+${FLOOR.x1}+${FLOOR.y1}`,
    "-compose",
    "over",
    "-composite",
    withFloor,
  ]);

  applyMaskedColor({
    base: withFloor,
    mask: LEFT_PAINT_MASK,
    color: COLORS.paint,
    outfile: withLeftPaint,
  });
  applyMaskedColor({
    base: withLeftPaint,
    mask: RIGHT_PAINT_MASK,
    color: COLORS.paint,
    outfile: withBothPaints,
  });

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
  applyMaskedColor({
    base: withBothPaints,
    mask: leftPaintOutline,
    color: COLORS.line,
    outfile: withLeftOutline,
  });
  applyMaskedColor({
    base: withLeftOutline,
    mask: rightPaintOutline,
    color: COLORS.line,
    outfile: withPaintOutlines,
  });

  const draw = [
    withPaintOutlines,

    "-fill", "none",
    "-stroke", COLORS.line,
    "-strokewidth", "8",
    "-draw", `line ${FLOOR.x1},${FLOOR_EDGE_TOP_Y} ${FLOOR.x2},${FLOOR_EDGE_TOP_Y}`,
    "-draw", `line ${FLOOR.x1},${FLOOR_EDGE_BOTTOM_Y} ${FLOOR.x2},${FLOOR_EDGE_BOTTOM_Y}`,
    "-draw", `line ${CENTER.x},${FLOOR.y1} ${CENTER.x},${FLOOR.y2}`,
    "-draw", `circle ${CENTER.x},${CENTER.y} ${CENTER.x},516`,

    "-draw", `path 'M ${THREE_POINT_LEFT.startX},${THREE_POINT_LEFT.topY} Q ${THREE_POINT_LEFT.controlX},${THREE_POINT_LEFT.topY} ${THREE_POINT_LEFT.controlX},1042 Q ${THREE_POINT_LEFT.controlX},${THREE_POINT_LEFT.bottomY} ${THREE_POINT_LEFT.startX},${THREE_POINT_LEFT.bottomY}'`,
    "-draw", `path 'M ${THREE_POINT_RIGHT.startX},${THREE_POINT_RIGHT.topY} Q ${THREE_POINT_RIGHT.controlX},${THREE_POINT_RIGHT.topY} ${THREE_POINT_RIGHT.controlX},1042 Q ${THREE_POINT_RIGHT.controlX},${THREE_POINT_RIGHT.bottomY} ${THREE_POINT_RIGHT.startX},${THREE_POINT_RIGHT.bottomY}'`,

    "-draw", `arc ${FREE_THROW_LEFT_BBOX.x1},${FREE_THROW_LEFT_BBOX.y1} ${FREE_THROW_LEFT_BBOX.x2},${FREE_THROW_LEFT_BBOX.y2} ${FREE_THROW_LEFT_BBOX.start},${FREE_THROW_LEFT_BBOX.end}`,
    "-draw", `arc ${FREE_THROW_RIGHT_BBOX.x1},${FREE_THROW_RIGHT_BBOX.y1} ${FREE_THROW_RIGHT_BBOX.x2},${FREE_THROW_RIGHT_BBOX.y2} ${FREE_THROW_RIGHT_BBOX.start},${FREE_THROW_RIGHT_BBOX.end}`,

    "-draw", `line ${KEY_HASHES_LEFT_X[0]},${KEY_HASH_TOP.y1} ${KEY_HASHES_LEFT_X[0]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[1]},${KEY_HASH_TOP.y1} ${KEY_HASHES_LEFT_X[1]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[2]},${KEY_HASH_TOP.y1} ${KEY_HASHES_LEFT_X[2]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[3]},${KEY_HASH_TOP.y1} ${KEY_HASHES_LEFT_X[3]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[0]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_LEFT_X[0]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[1]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_LEFT_X[1]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[2]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_LEFT_X[2]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_LEFT_X[3]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_LEFT_X[3]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[0]},${KEY_HASH_TOP.y1} ${KEY_HASHES_RIGHT_X[0]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[1]},${KEY_HASH_TOP.y1} ${KEY_HASHES_RIGHT_X[1]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[2]},${KEY_HASH_TOP.y1} ${KEY_HASHES_RIGHT_X[2]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[3]},${KEY_HASH_TOP.y1} ${KEY_HASHES_RIGHT_X[3]},${KEY_HASH_TOP.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[0]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_RIGHT_X[0]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[1]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_RIGHT_X[1]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[2]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_RIGHT_X[2]},${KEY_HASH_BOTTOM.y2}`,
    "-draw", `line ${KEY_HASHES_RIGHT_X[3]},${KEY_HASH_BOTTOM.y1} ${KEY_HASHES_RIGHT_X[3]},${KEY_HASH_BOTTOM.y2}`,

    "-quality", "92",
    output,
  ];

  run(draw);

  if (existsSync(LEFT_BASKET_ALPHA) && existsSync(RIGHT_BASKET_ALPHA)) {
    run([
      output,
      LEFT_BASKET_ALPHA, "-geometry", "+126+892", "-compose", "over", "-composite",
      RIGHT_BASKET_ALPHA, "-geometry", "+3042+892", "-compose", "over", "-composite",
      "-quality", "92",
      output,
    ]);
  } else {
    run([
      output,
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
      "-stroke", "#ffffff",
      "-strokewidth", "3",
      "-draw", `line ${RIM_LEFT.x - 20},${RIM_LEFT.y + 10} ${RIM_LEFT.x},${RIM_LEFT.y + 55}`,
      "-draw", `line ${RIM_LEFT.x + 20},${RIM_LEFT.y + 10} ${RIM_LEFT.x},${RIM_LEFT.y + 55}`,
      "-draw", `line ${RIM_LEFT.x - 34},${RIM_LEFT.y + 10} ${RIM_LEFT.x - 12},${RIM_LEFT.y + 70}`,
      "-draw", `line ${RIM_LEFT.x + 34},${RIM_LEFT.y + 10} ${RIM_LEFT.x + 12},${RIM_LEFT.y + 70}`,
      "-draw", `line ${RIM_RIGHT.x - 20},${RIM_RIGHT.y + 10} ${RIM_RIGHT.x},${RIM_RIGHT.y + 55}`,
      "-draw", `line ${RIM_RIGHT.x + 20},${RIM_RIGHT.y + 10} ${RIM_RIGHT.x},${RIM_RIGHT.y + 55}`,
      "-draw", `line ${RIM_RIGHT.x - 34},${RIM_RIGHT.y + 10} ${RIM_RIGHT.x - 12},${RIM_RIGHT.y + 70}`,
      "-draw", `line ${RIM_RIGHT.x + 34},${RIM_RIGHT.y + 10} ${RIM_RIGHT.x + 12},${RIM_RIGHT.y + 70}`,
      "-quality", "92",
      output,
    ]);
  }
  process.stdout.write(`${output}\n`);
}

main();
