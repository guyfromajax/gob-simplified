#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SOURCE = path.join(
  ROOT,
  "FrontEnd/static/images/teams/bentley_truman/bentley_truman_court.jpg",
);
const OUTDIR = path.join(ROOT, "tmp/court-template");
const WORKDIR = path.join(OUTDIR, "neutral-work");
const REFERENCE_COURTS = [
  "bentley_truman",
  "lancaster",
  "four_corners",
  "morristown",
  "ocean_city",
  "little_york",
  "xavien",
  "south_lancaster",
].map((slug) => path.join(ROOT, `FrontEnd/static/images/teams/${slug}/${slug}_court.jpg`));

const COLORS = {
  border: "#000000",
  line: "#6e675f",
  hardwood: "#ecdbc9",
};

const BOXES = {
  leftBorder: { x1: 0, y1: 0, x2: 190, y2: 2083 },
  rightBorder: { x1: 3143, y1: 0, x2: 3333, y2: 2083 },
  centerCover: { x1: 1240, y1: 610, x2: 2090, y2: 1425 },
  leftTopCover: { x1: 360, y1: 180, x2: 1040, y2: 820 },
  leftBottomCover: { x1: 360, y1: 1240, x2: 1040, y2: 1890 },
  rightTopCover: { x1: 2290, y1: 180, x2: 2970, y2: 820 },
  rightBottomCover: { x1: 2290, y1: 1240, x2: 2970, y2: 1890 },
};

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function run(args) {
  execFileSync("magick", args, { stdio: "pipe" });
}

function coverWithPatch({ base, patchSource, box, outfile }) {
  const width = box.x2 - box.x1;
  const height = box.y2 - box.y1;
  const patch = path.join(
    WORKDIR,
    `${path.basename(outfile, ".jpg")}_${box.x1}_${box.y1}_${box.x2}_${box.y2}.jpg`,
  );
  run([
    patchSource,
    "-crop",
    `${width}x${height}+${box.x1}+${box.y1}`,
    "+repage",
    patch,
  ]);
  run([
    base,
    "(",
    patch,
    "-resize",
    `${width}x${height}!`,
    ")",
    "-geometry",
    `+${box.x1}+${box.y1}`,
    "-compose",
    "over",
    "-composite",
    outfile,
  ]);
}

function main() {
  ensureDir(OUTDIR);
  ensureDir(WORKDIR);

  const meanComposite = path.join(WORKDIR, "mean_reference.jpg");
  const meanCompositeBlur = path.join(WORKDIR, "mean_reference_blur12.jpg");
  const step1 = path.join(WORKDIR, "step1.jpg");
  const step2 = path.join(WORKDIR, "step2.jpg");
  const step3 = path.join(WORKDIR, "step3.jpg");
  const step4 = path.join(WORKDIR, "step4.jpg");
  const neutral = path.join(OUTDIR, "master_neutral_court_base.jpg");

  run([...REFERENCE_COURTS, "-evaluate-sequence", "Mean", meanComposite]);
  run([meanComposite, "-blur", "0x12", meanCompositeBlur]);

  coverWithPatch({ base: SOURCE, patchSource: meanCompositeBlur, box: BOXES.centerCover, outfile: step1 });
  coverWithPatch({ base: step1, patchSource: meanCompositeBlur, box: BOXES.leftTopCover, outfile: step2 });
  coverWithPatch({ base: step2, patchSource: meanCompositeBlur, box: BOXES.leftBottomCover, outfile: step3 });
  coverWithPatch({ base: step3, patchSource: meanCompositeBlur, box: BOXES.rightTopCover, outfile: step4 });
  coverWithPatch({ base: step4, patchSource: meanCompositeBlur, box: BOXES.rightBottomCover, outfile: neutral });

  run([
    neutral,
    "-fill",
    COLORS.border,
    "-draw",
    `rectangle ${BOXES.leftBorder.x1},${BOXES.leftBorder.y1} ${BOXES.leftBorder.x2 - 1},${BOXES.leftBorder.y2 - 1}`,
    "-draw",
    `rectangle ${BOXES.rightBorder.x1},${BOXES.rightBorder.y1} ${BOXES.rightBorder.x2 - 1},${BOXES.rightBorder.y2 - 1}`,
    "-stroke",
    COLORS.line,
    "-strokewidth",
    "10",
    "-fill",
    "none",
    "-draw",
    "line 1666,62 1666,2020",
    "-draw",
    "circle 1666,1042 1666,515",
    "-quality",
    "92",
    neutral,
  ]);

  process.stdout.write(`${neutral}\n`);
}

main();
