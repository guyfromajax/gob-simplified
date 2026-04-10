#!/usr/bin/env node

import fs from 'fs';
import os from 'os';
import path from 'path';
import { spawnSync } from 'child_process';

const ROOT = process.cwd();
const TEAM_FILE = path.join(ROOT, 'teams', '128_teams.txt');
const TEAM_IMAGE_ROOT = path.join(ROOT, 'FrontEnd', 'static', 'images', 'teams');
const OUTPUT_DIR = path.join(ROOT, 'tmp', 'team-logo-pipeline');
const RAW_OUTPUT_DIR = path.join(OUTPUT_DIR, 'raw');
const LOGO_TARGET_WIDTH = 320;
const LOGO_TARGET_HEIGHT = 268;
const BANNER_TARGET_WIDTH = 1920;
const BANNER_TARGET_HEIGHT = 679;
const BANNER_GENERATION_SIZE = '1536x1024';
const OPENAI_IMAGE_API_URL = 'https://api.openai.com/v1/images/generations';
const DEFAULT_IMAGE_MODEL = 'gpt-image-1.5';

const ASSET_SPECS = [
  { key: 'banner_primary', ext: 'jpg' },
  { key: 'logo_square', ext: 'png' },
  { key: 'court', ext: 'jpg' },
  { key: 'background', ext: 'png' }
];

function nameToSlug(teamName) {
  return String(teamName || '')
    .trim()
    .toLowerCase()
    .replace(/['.]/g, '')
    .replace(/-/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\s/g, '_');
}

function parseTeamsFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  const lines = raw.split(/\r?\n/);
  const teams = [];
  for (let i = 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;
    if (line === 'prestige_rankings') break;
    let cols = line.split('\t');
    if (!/^\d+$/.test(cols[0])) continue;
    if (cols.length === 8) {
      const colorMatches = String(cols[4]).match(/#[0-9a-fA-F]{6}/g);
      if (colorMatches && colorMatches.length >= 2) {
        cols = [
          cols[0],
          cols[1],
          cols[2],
          cols[3],
          colorMatches[0],
          colorMatches[1],
          cols[5],
          cols[6],
          cols[7]
        ];
      }
    }
    if (cols.length < 9) continue;
    teams.push({
      id: Number(cols[0]),
      team: cols[1],
      mascot: cols[2],
      team_id: cols[3],
      primary_color: cols[4],
      secondary_color: cols[5],
      conference: cols[6],
      region: cols[7],
      prestige: Number(cols[8]),
      slug: nameToSlug(cols[1])
    });
  }
  return teams;
}

function getDirStatus(slug) {
  const teamDir = path.join(TEAM_IMAGE_ROOT, slug);
  if (!fs.existsSync(teamDir) || !fs.statSync(teamDir).isDirectory()) {
    return {
      dirExists: false,
      assets: ASSET_SPECS.map((spec) => ({
        ...spec,
        expectedPath: path.join(teamDir, `${slug}_${spec.key}.${spec.ext}`),
        exists: false
      }))
    };
  }

  const assets = ASSET_SPECS.map((spec) => {
    const expectedPath = path.join(teamDir, `${slug}_${spec.key}.${spec.ext}`);
    return {
      ...spec,
      expectedPath,
      exists: fs.existsSync(expectedPath)
    };
  });

  return { dirExists: true, assets };
}

function buildPrompt(team) {
  return [
    `Create a sports logo for the fictional basketball program "${team.team} ${team.mascot}".`,
    `Use the primary team color ${team.primary_color} and secondary color ${team.secondary_color}.`,
    'Style: polished collegiate identity mark, bold silhouette, strong contrast, clean vector-like edges, centered composition.',
    'Output focus: transparent-background logo mark only, no jersey mockup, no stadium, no text outside the team identity, no watermark.',
    'Keep the design readable at small sizes and suitable for a square crop.'
  ].join(' ');
}

function buildLogoPrompt(team) {
  const mascotDirection = describeMascotDirection(team.mascot);
  const teamSpecificNote = getTeamSpecificPromptNote(team);
  return [
    `Design a premium fictional basketball team logo for "${team.team}" with mascot "${team.mascot}".`,
    `Primary color: ${team.primary_color}. Secondary color: ${team.secondary_color}.`,
    `The visual identity should clearly evoke the ${team.mascot} mascot theme.`,
    mascotDirection.logoLead,
    teamSpecificNote.logo,
    'The result must be a single centered logo mark or crest on a transparent background.',
    'No background scene, no mockup, no jersey, no court, no frame, no extra objects.',
    'No tiny decorative text. If text appears at all, keep it minimal, bold, and integrated into the mark.',
    'Make it feel like a polished modern collegiate sports identity with crisp edges and strong silhouette recognition.'
  ].filter(Boolean).join(' ');
}

function buildBannerPrompt(team) {
  const mascotDirection = describeMascotDirection(team.mascot);
  const teamSpecificNote = getTeamSpecificPromptNote(team);
  return [
    'Create a premium American sports team banner logo.',
    '',
    'IMAGE SIZE',
    `Generate the image at: ${BANNER_GENERATION_SIZE} resolution.`,
    `Compose it so it can be safely auto-exported to ${BANNER_TARGET_WIDTH} x ${BANNER_TARGET_HEIGHT} without losing key content.`,
    'Use a very wide horizontal banner composition with the important content centered vertically.',
    '',
    'TEAM',
    `${team.team} ${team.mascot}`,
    '',
    'LAYOUT',
    'Mascot icon on the left.',
    'Wordmark on the right.',
    '',
    'TEXT',
    '',
    'Top line (smaller):',
    team.team.toUpperCase(),
    '',
    'Bottom line (large):',
    team.mascot.toUpperCase(),
    '',
    'MASCOT',
    mascotDirection.bannerLead,
    mascotDirection.bannerEnergy,
    mascotDirection.bannerFacing,
    teamSpecificNote.banner,
    '',
    'MASCOT STYLE',
    '',
    'Vector sports mascot illustration similar to modern NCAA or NFL team logos.',
    '',
    'The mascot should be:',
    'bold geometric shapes',
    'thick outlines',
    'simple 2-3 tone shading',
    'high contrast',
    'strong silhouette',
    '',
    'Avoid:',
    'photorealism',
    'painterly textures',
    'thin lines',
    'cartoon style',
    'full body characters',
    '',
    'CRITICAL MASCOT SIZE CONSTRAINT',
    '',
    'The mascot must occupy only about 30-35% of the total image height.',
    'Leave generous empty space above and below the mascot.',
    'The mascot must never touch the top or bottom edge of the image.',
    'Only show a head or icon, not a torso or full body.',
    `Keep all important design elements inside a safe center band so the image can be automatically exported to ${BANNER_TARGET_WIDTH} x ${BANNER_TARGET_HEIGHT}.`,
    '',
    'COLORS - STRICT PALETTE',
    '',
    `Primary color: ${team.primary_color}`,
    `Secondary color: ${team.secondary_color}`,
    '',
    'IMPORTANT COLOR RULES',
    '',
    `Use ${team.primary_color} as the dominant background color.`,
    `Use ${team.secondary_color} for wordmark accents, outlines, and highlights.`,
    `Any shading must stay within the ${team.secondary_color} color family.`,
    'Do not introduce unrelated accent colors.',
    '',
    'BACKGROUND',
    '',
    `Use a background gradient built from ${team.primary_color}.`,
    mascotDirection.bannerWatermark,
    'Use subtle sports texture.',
    '',
    'TYPOGRAPHY',
    '',
    'Bold collegiate athletic font.',
    'High readability.',
    '',
    'COMPOSITION',
    '',
    'Mascot slightly overlaps the wordmark.',
    'Balanced professional sports branding.',
    'Premium NCAA / NFL quality look.'
  ].join('\n');
}

function getTeamSpecificPromptNote(team) {
  const slug = String(team?.slug || nameToSlug(team?.team || '')).toLowerCase();
  const notes = {
    abilene: {
      banner: 'Use a true scorpion as the hero subject. Do not depict any snake, serpent, cobra, rattlesnake, or snake head. Make the scorpion anatomy unmistakable, with visible claws, segmented tail, and stinger.',
      logo: 'Use an unmistakable scorpion identity. Do not use any snake or serpent form. The mark should clearly read as a scorpion with claws and a raised stinger.'
    },
    bayou_district: {
      banner: 'Use the airboat as the clear hero subject. Do not use an alligator, crocodile, reptile, or animal head as the mascot. Make the airboat silhouette unmistakable, with the fan cage and hull clearly visible, and keep the identity centered on speed, swamp navigation, and mechanical power. The bottom wordmark must spell AIRBOATS exactly: A-I-R-B-O-A-T-S.',
      logo: 'Use a true airboat identity rather than any animal mascot. The mark should clearly read as an airboat with a visible fan cage and hull, not an alligator or reptile. If the mascot word appears, it must be spelled AIRBOATS exactly: A-I-R-B-O-A-T-S.'
    },
    boise: {
      banner: 'Use a true mountaineer as the hero subject. Do not use any bird, eagle, hawk, falcon, owl, wing, beak, feathers, or avian silhouette. Make the identity read as a rugged human alpine figure with clear mountain character, expedition toughness, and elevated frontier confidence.',
      logo: 'Use a human mountaineer identity rather than any bird mascot. The mark should clearly read as an original alpine explorer or mountain man figure, not an avian form.'
    },
    desert_regional: {
      banner: 'Use a mesa as the clear hero concept. Do not use any bird, eagle, hawk, falcon, owl, wing, beak, feathers, or bird head. Create an original, creative mesa-based identity built around desert rock formations, layered stone shapes, canyon geometry, and monumental Southwest landscape power.',
      logo: 'Use a mesa-based identity rather than any bird mascot. The mark should clearly read as a bold, original mesa or desert-rock emblem with strong silhouette and no avian elements.'
    },
    gp_prep_school: {
      banner: 'Do not use any bird, eagle, hawk, falcon, owl, wing, beak, feathers, or avian silhouette. Use a "perfect being" approach: create an original elite transcendent figure or emblem inspired by the calm, godlike, hyper-idealized presence of Dr. Manhattan from Watchmen, but do not directly copy that character. The identity should convey perfection, superiority, control, evolved power, and composed dominance.',
      logo: 'Use an original perfect-being identity rather than any bird mascot. Create an elite transcendent figure or emblem that feels calm, godlike, hyper-idealized, and superior, without directly copying any existing character.'
    },
    huntington_canyon: {
      banner: 'Create a true ranger identity rather than a cowboy. Do not use a bandana. Add a star on the hat. Give the face a more chiseled, angular structure with a clear ranger-lawman feel. Keep the character distinct from the Houston Jesuit cowboy by emphasizing frontier authority, canyon patrol toughness, and ranger symbolism rather than outlaw or rodeo styling.',
      logo: 'Use a ranger-lawman identity rather than a cowboy. Include a star on the hat, remove the bandana, and give the face a chiseled, angular ranger look distinct from a generic cowboy mascot.'
    },
    southwest_miner: {
      banner: 'Do not use a cowboy face, bandit face, ranger face, or human head as the mascot. Use a dynamic pair of cowboy boots with spurs as the clear hero concept. The identity should feel bold, unorthodox, rugged, and Southwestern, with the boots driving the composition as the main emblem.',
      logo: 'Use a bold pair of cowboy boots with spurs as the mascot identity rather than any cowboy or human face. The mark should feel rugged, Southwestern, and visually distinctive.'
    },
    middletex: {
      banner: 'Keep the team name styled exactly as MiddleTEX, with TEX in full capitals. The top line must read exactly: MiddleTEX. Use a true bucking bronco identity with strong Western athletic energy. Make the bronco the clear hero subject and avoid generic or softened horse imagery.',
      logo: 'Keep the team name styled exactly as MiddleTEX, with TEX in full capitals. Use a bold bucking bronco identity with strong Western energy and clear horse motion.'
    }
  };
  return notes[slug] || { banner: '', logo: '' };
}

function describeMascotDirection(mascot) {
  const raw = String(mascot || '').trim();
  const lower = raw.toLowerCase();
  const overrides = {
    academy: {
      bannerLead: 'Create a bold academic crest or institutional emblem rather than a literal creature mascot.',
      bannerEnergy: 'The mark should feel prestigious, disciplined, and elite, with clean competitive authority.',
      bannerFacing: 'Orient the main emblem toward the center of the banner.',
      bannerWatermark: 'Add a large faded crest or shield watermark behind the logo that reinforces the Academy identity.',
      logoLead: 'Use a premium academic crest or shield mark rather than an animal mascot.'
    },
    collective: {
      bannerLead: 'Create a modern symbolic identity mark or crest rather than a literal creature mascot.',
      bannerEnergy: 'The symbol should feel elite, unified, and forward-looking, with a premium global-sports identity.',
      bannerFacing: 'Orient the main symbol toward the center of the banner.',
      bannerWatermark: 'Add a large faded symbolic watermark behind the logo that reinforces the Collective identity.',
      logoLead: 'Use a modern symbolic crest or identity mark that conveys the Collective theme.'
    },
    'red wave': {
      bannerLead: 'Create a dynamic symbolic mascot mark built around wave motion, force, and momentum rather than a literal creature head.',
      bannerEnergy: 'The mark should feel explosive, fast, and overwhelming, with aggressive motion and clean sports-logo geometry.',
      bannerFacing: 'Orient the motion so it drives toward the center of the banner.',
      bannerWatermark: 'Add a large faded wave-form watermark behind the logo that reinforces the Red Wave identity.',
      logoLead: 'Use a dynamic wave-based sports mark rather than an animal mascot.'
    },
    legion: {
      bannerLead: 'Create a disciplined crest or warrior-inspired emblem rather than a literal creature mascot.',
      bannerEnergy: 'The emblem should feel organized, imposing, and elite, with strong authority and premium sports branding.',
      bannerFacing: 'Orient the main emblem toward the center of the banner.',
      bannerWatermark: 'Add a large faded crest or emblem watermark behind the logo that reinforces the Legion identity.',
      logoLead: 'Use a disciplined crest or warrior-inspired emblem that fits the Legion identity.'
    },
    waterfalls: {
      bannerLead: 'Create a stylized symbolic identity mark built around cascading water, vertical force, and natural power rather than a literal creature mascot.',
      bannerEnergy: 'The symbol should feel fluid, dramatic, and dominant, with strong motion and premium sports-logo structure.',
      bannerFacing: 'Orient the flow so the composition pulls toward the center of the banner.',
      bannerWatermark: 'Add a large faded cascading-water watermark behind the logo that reinforces the Waterfalls identity.',
      logoLead: 'Use a dynamic water-based identity mark rather than an animal mascot.'
    },
    sky: {
      bannerLead: 'Create a stylized symbolic identity mark based on sky, altitude, and open-air motion rather than a literal creature mascot.',
      bannerEnergy: 'The symbol should feel expansive, fast, and elevated, with premium sports-logo clarity.',
      bannerFacing: 'Orient the motion so it pulls toward the center of the banner.',
      bannerWatermark: 'Add a large faded atmospheric or sky-form watermark behind the logo that reinforces the Sky identity.',
      logoLead: 'Use a premium sky-inspired symbolic mark rather than an animal mascot.'
    },
    chill: {
      bannerLead: 'Create a sharp symbolic identity mark built around cold, control, and composure rather than a literal creature mascot.',
      bannerEnergy: 'The symbol should feel cool, disciplined, and dangerous, with premium sports-logo structure.',
      bannerFacing: 'Orient the main shape toward the center of the banner.',
      bannerWatermark: 'Add a large faded cold-themed watermark behind the logo that reinforces the Chill identity.',
      logoLead: 'Use a cold-themed symbolic sports mark rather than an animal mascot.'
    },
    sound: {
      bannerLead: 'Create a symbolic identity mark built around sound waves, rhythm, and pressure rather than a literal creature mascot.',
      bannerEnergy: 'The symbol should feel modern, loud, and forceful, with clean sports-logo geometry.',
      bannerFacing: 'Orient the motion toward the center of the banner.',
      bannerWatermark: 'Add a large faded sound-wave watermark behind the logo that reinforces the Sound identity.',
      logoLead: 'Use a sound-wave or audio-inspired sports mark rather than an animal mascot.'
    },
    squad: {
      bannerLead: 'Create a bold all-star emblem or symbolic crest rather than a literal creature mascot.',
      bannerEnergy: 'The mark should feel elite, celebratory, and competitive, with premium sports-brand authority.',
      bannerFacing: 'Orient the emblem toward the center of the banner.',
      bannerWatermark: 'Add a large faded all-star emblem watermark behind the logo that reinforces the Squad identity.',
      logoLead: 'Use a premium all-star emblem or crest rather than an animal mascot.'
    }
  };

  if (overrides[lower]) return overrides[lower];

  const sets = {
    abstract: new Set([
      'academy', 'collective', 'legion', 'red wave', 'sky', 'chill', 'sound', 'squad',
      'force', 'patrol', 'thunder', 'harvest'
    ]),
    military: new Set([
      'admirals', 'captains', 'generals', 'sentinels', 'knights', 'sterling knights',
      'blackjacks', 'regents', 'royals', 'monarchs', 'swordsmen', 'patriots', 'defenders'
    ]),
    people: new Set([
      'minutemen', 'sailors', 'orioles', 'cavalry', 'hitmen', 'climbers', 'engineers',
      'fishermen', 'carriers', 'ringmasters', 'saloon'
    ]),
    snake: new Set(['rattlesnakes', 'ratsnakes', 'diamondbacks', 'cobras', 'scorpions']),
    bird: new Set([
      'hawks', 'golden eagles', 'eagles', 'falcons', 'owls', 'pelicans', 'orioles',
      'cardinals', 'admirals', 'mountaineers'
    ]),
    marine: new Set(['sea turtles', 'airboats', 'mariners', 'breakers', 'catfish', 'dolphins', 'sharks']),
    beast: new Set([
      'wildcats', 'bears', 'bobcats', 'panthers', 'wolves', 'coyotes', 'wolverines',
      'huskies', 'mustangs', 'bullldogs', 'bulldogs', 'beavers', 'armadillos',
      'caribou', 'woodchucks', 'cougars', 'leopards', 'grizzlies', 'wasps'
    ])
  };

  const make = (lead, energy, facing, watermark, logoLead = lead) => ({
    bannerLead: lead,
    bannerEnergy: energy,
    bannerFacing: facing,
    bannerWatermark: watermark,
    logoLead
  });

  if (sets.abstract.has(lower)) {
    return make(
      `Create a stylized identity mark based on the ${raw} theme rather than a literal animal head.`,
      'The symbol should feel bold, competitive, and premium, with strong motion or authority.',
      'Orient the main shape so the composition pulls toward the center of the banner.',
      `Add a large faded symbolic watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use a bold symbolic crest or abstract identity mark that clearly reflects the ${raw} theme.`
    );
  }

  if (sets.military.has(lower)) {
    return make(
      `Create a stylized mascot icon or crest based on the ${raw} identity.`,
      'The icon should feel disciplined, commanding, and authoritative, with a premium competitive edge.',
      'Orient the main emblem toward the center of the banner.',
      `Add a large faded emblem or mascot watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use a premium crest or emblem that clearly evokes the ${raw} identity.`
    );
  }

  if (sets.people.has(lower)) {
    return make(
      `Create a stylized character icon based on the ${raw} identity.`,
      'The character should feel sharp, confident, and competitive, simplified into a strong sports-logo silhouette.',
      'The icon should face toward the center of the banner.',
      `Add a large faded silhouette watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use a stylized character-driven sports mark that clearly evokes the ${raw} identity.`
    );
  }

  if (sets.snake.has(lower)) {
    return make(
      `Create a stylized serpent mascot icon based on the ${raw} identity.`,
      'The mascot should feel aggressive, fast, and dangerous, with a sharp predatory presence.',
      'The mascot should face toward the center of the banner.',
      `Add a large faded serpent-head watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use a sharp serpent-based sports mark that clearly evokes the ${raw} identity.`
    );
  }

  if (sets.bird.has(lower)) {
    return make(
      `Create a stylized bird mascot icon based on the ${raw} identity.`,
      'The mascot should feel fast, sharp, and dominant, with strong attitude and competitive energy.',
      'The mascot should face toward the center of the banner.',
      `Add a large faded bird-head silhouette watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use a sharp bird-based sports mark that clearly evokes the ${raw} identity.`
    );
  }

  if (sets.marine.has(lower)) {
    return make(
      `Create a stylized aquatic or nautical mascot icon based on the ${raw} identity.`,
      'The mascot should feel powerful, fluid, and competitive, with clean aggressive shapes.',
      'The mascot should face or flow toward the center of the banner.',
      `Add a large faded aquatic-themed watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use an aquatic or nautical sports mark that clearly evokes the ${raw} identity.`
    );
  }

  if (sets.beast.has(lower)) {
    return make(
      `Create a stylized animal mascot icon based on the ${raw} identity.`,
      'The mascot should feel fierce, athletic, and dominant, with strong attitude and clean silhouette recognition.',
      'The mascot should face toward the center of the banner.',
      `Add a large faded animal-head silhouette watermark behind the logo that clearly reflects the ${raw} identity.`,
      `Use an aggressive animal-based sports mark that clearly evokes the ${raw} identity.`
    );
  }

  return make(
    `Create a stylized mascot icon based on the ${raw} identity.`,
    'The mascot should feel fast, sharp, and dominant, with strong attitude and competitive energy.',
    'The mascot should face toward the center of the banner.',
    `Add a large faded mascot silhouette watermark behind the logo that clearly reflects the ${raw} identity.`,
    `Use a premium sports mark that clearly evokes the ${raw} identity.`
  );
}

function buildManifest(teams) {
  return teams.map((team) => {
    const status = getDirStatus(team.slug);
    const presentAssets = status.assets.filter((asset) => asset.exists).map((asset) => asset.key);
    const missingAssets = status.assets.filter((asset) => !asset.exists).map((asset) => asset.key);
    return {
      ...team,
      team_dir: `FrontEnd/static/images/teams/${team.slug}`,
      expected_files: Object.fromEntries(
        status.assets.map((asset) => [
          asset.key,
          `FrontEnd/static/images/teams/${team.slug}/${team.slug}_${asset.key}.${asset.ext}`
        ])
      ),
      dir_exists: status.dirExists,
      present_assets: presentAssets,
      missing_assets: missingAssets,
      prompt: buildPrompt(team),
      logo_prompt: buildLogoPrompt(team),
      banner_prompt: buildBannerPrompt(team)
    };
  });
}

function ensureOutputDir() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

function writeJson(fileName, value) {
  ensureOutputDir();
  const target = path.join(OUTPUT_DIR, fileName);
  fs.writeFileSync(target, JSON.stringify(value, null, 2) + '\n', 'utf8');
  return target;
}

function printAudit(teams) {
  const manifest = buildManifest(teams);
  const missingDirs = manifest.filter((row) => !row.dir_exists);
  const completeTeams = manifest.filter((row) => row.missing_assets.length === 0);
  const partialTeams = manifest.filter((row) => row.dir_exists && row.missing_assets.length > 0);

  const summary = {
    teamCount: manifest.length,
    completeTeams: completeTeams.length,
    partialTeams: partialTeams.length,
    missingDirs: missingDirs.length,
    missingDirSlugs: missingDirs.map((row) => row.slug),
    partialTeamSample: partialTeams.slice(0, 20).map((row) => ({
      slug: row.slug,
      present_assets: row.present_assets,
      missing_assets: row.missing_assets
    }))
  };

  console.log(JSON.stringify(summary, null, 2));
}

function writeManifest(teams) {
  const manifest = buildManifest(teams);
  const target = writeJson('team-logo-manifest.json', manifest);
  console.log(target);
}

function writePrompts(teams) {
  const prompts = buildManifest(teams)
    .map((row) => ({
      slug: row.slug,
      team: row.team,
      mascot: row.mascot,
      logo_prompt: row.logo_prompt,
      banner_prompt: row.banner_prompt
    }));
  const target = writeJson('team-logo-prompts.json', prompts);
  console.log(target);
}

function parseArgs(args) {
  const parsed = { _: [] };
  const normalizeKey = (key) => key.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (!arg.startsWith('--')) {
      parsed._.push(arg);
      continue;
    }
    const eq = arg.indexOf('=');
    if (eq !== -1) {
      parsed[normalizeKey(arg.slice(2, eq))] = arg.slice(eq + 1);
      continue;
    }
    const key = normalizeKey(arg.slice(2));
    const next = args[i + 1];
    if (!next || next.startsWith('--')) {
      parsed[key] = true;
      continue;
    }
    parsed[key] = next;
    i += 1;
  }
  return parsed;
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function ensureToolAvailable(name) {
  const result = spawnSync('bash', ['-lc', `command -v ${name}`], { encoding: 'utf8' });
  if (result.status !== 0) {
    throw new Error(`Required tool is not available: ${name}`);
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function pickTeamsForLogoGeneration(teams, options = {}) {
  const manifest = buildManifest(teams);
  let rows = manifest.filter((row) => !row.present_assets.includes('logo_square'));
  if (options.team) {
    const wanted = String(options.team).toLowerCase();
    rows = manifest.filter((row) => row.slug === wanted || row.team.toLowerCase() === wanted);
  }
  if (options.force) {
    rows = manifest.filter((row) => {
      if (!options.team) return true;
      const wanted = String(options.team).toLowerCase();
      return row.slug === wanted || row.team.toLowerCase() === wanted;
    });
  }
  const limit = options.limit ? Number(options.limit) : null;
  if (limit && Number.isFinite(limit) && limit > 0) rows = rows.slice(0, limit);
  return rows;
}

async function generateImageBase64(prompt, options = {}) {
  const apiKey = requireEnv('OPENAI_API_KEY');
  const model = options.model || DEFAULT_IMAGE_MODEL;
  const response = await fetch(OPENAI_IMAGE_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model,
      prompt,
      size: options.size || '1024x1024',
      quality: options.quality || 'high',
      background: options.background || 'transparent',
      output_format: options.outputFormat || 'png',
      moderation: options.moderation || 'low',
      n: 1
    })
  });

  if (!response.ok) {
    const text = await response.text();
    if (response.status === 400 && text.includes('billing_hard_limit_reached')) {
      throw new Error('OpenAI image generation failed: billing hard limit reached. Check your API billing/usage limits.');
    }
    if (response.status === 400 && text.includes('model')) {
      throw new Error(`OpenAI image generation failed for model "${model}". Your account may not have access to it yet. Raw response: ${text}`);
    }
    throw new Error(`OpenAI image generation failed (${response.status}): ${text}`);
  }

  const json = await response.json();
  const base64 = json?.data?.[0]?.b64_json;
  if (!base64) {
    throw new Error('OpenAI image generation returned no image data');
  }
  return base64;
}

function normalizeLogo(rawPath, outPath) {
  const result = spawnSync(
    'magick',
    [
      rawPath,
      '-trim',
      '+repage',
      '-resize',
      `${LOGO_TARGET_WIDTH}x${LOGO_TARGET_HEIGHT}>`,
      '-background',
      'none',
      '-gravity',
      'center',
      '-extent',
      `${LOGO_TARGET_WIDTH}x${LOGO_TARGET_HEIGHT}`,
      outPath
    ],
    { encoding: 'utf8' }
  );

  if (result.status !== 0) {
    throw new Error(`ImageMagick normalize failed: ${result.stderr || result.stdout}`);
  }
}

function writeRawLogo(base64, slug) {
  ensureDir(RAW_OUTPUT_DIR);
  const filePath = path.join(RAW_OUTPUT_DIR, `${slug}_logo_raw.png`);
  fs.writeFileSync(filePath, Buffer.from(base64, 'base64'));
  return filePath;
}

function writeFinalLogo(slug, rawPath) {
  const teamDir = path.join(TEAM_IMAGE_ROOT, slug);
  ensureDir(teamDir);
  const outPath = path.join(teamDir, `${slug}_logo_square.png`);
  normalizeLogo(rawPath, outPath);
  return outPath;
}

function normalizeBanner(rawPath, outPath) {
  const result = spawnSync(
    'magick',
    [
      rawPath,
      '-resize',
      `${BANNER_TARGET_WIDTH}x${BANNER_TARGET_HEIGHT}^`,
      '-gravity',
      'center',
      '-extent',
      `${BANNER_TARGET_WIDTH}x${BANNER_TARGET_HEIGHT}`,
      '-strip',
      '-quality',
      '92',
      outPath
    ],
    { encoding: 'utf8' }
  );

  if (result.status !== 0) {
    throw new Error(`ImageMagick banner normalize failed: ${result.stderr || result.stdout}`);
  }
}

function writeRawBanner(base64, slug) {
  const rawDir = path.join(RAW_OUTPUT_DIR, 'banners');
  ensureDir(rawDir);
  const filePath = path.join(rawDir, `${slug}_banner_raw.jpg`);
  fs.writeFileSync(filePath, Buffer.from(base64, 'base64'));
  return filePath;
}

function writeFinalBanner(slug, rawPath) {
  const teamDir = path.join(TEAM_IMAGE_ROOT, slug);
  ensureDir(teamDir);
  const outPath = path.join(teamDir, `${slug}_banner_primary.jpg`);
  normalizeBanner(rawPath, outPath);
  return outPath;
}

function pickTeamsForBannerGeneration(teams, options = {}) {
  const manifest = buildManifest(teams);
  let rows = manifest.filter((row) => !row.present_assets.includes('banner_primary'));
  if (options.team) {
    const wanted = String(options.team).toLowerCase();
    rows = manifest.filter((row) => row.slug === wanted || row.team.toLowerCase() === wanted);
  }
  if (options.force) {
    rows = manifest.filter((row) => {
      if (!options.team) return true;
      const wanted = String(options.team).toLowerCase();
      return row.slug === wanted || row.team.toLowerCase() === wanted;
    });
  }
  const limit = options.limit ? Number(options.limit) : null;
  if (limit && Number.isFinite(limit) && limit > 0) rows = rows.slice(0, limit);
  return rows;
}

function normalizeExistingBanners(teams, options = {}) {
  const rows = pickTeamsForBannerGeneration(teams, { ...options, force: true })
    .filter((row) => fs.existsSync(path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_banner_primary.jpg`)));

  if (options.team) {
    const wanted = String(options.team).toLowerCase();
    const exact = buildManifest(teams).filter((row) => {
      const isMatch = row.slug === wanted || row.team.toLowerCase() === wanted;
      return isMatch && fs.existsSync(path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_banner_primary.jpg`));
    });
    rows.length = 0;
    rows.push(...exact);
  }

  if (!rows.length) {
    console.log('No existing banner_primary files matched for normalization.');
    return;
  }

  const summary = [];
  for (const row of rows) {
    const finalPath = path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_banner_primary.jpg`);
    const tmpPath = path.join(os.tmpdir(), `${row.slug}_banner_primary_normalize.jpg`);
    fs.copyFileSync(finalPath, tmpPath);
    normalizeBanner(tmpPath, finalPath);
    fs.unlinkSync(tmpPath);
    summary.push({ slug: row.slug, finalPath, status: 'normalized' });
    console.log(`${row.slug}: ${finalPath}`);
  }
  const target = writeJson('team-banner-normalize-summary.json', summary);
  console.log(`Summary: ${target}`);
}

function normalizeExistingLogos(teams, options = {}) {
  const rows = pickTeamsForLogoGeneration(teams, { ...options, force: true })
    .filter((row) => fs.existsSync(path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_logo_square.png`)));

  if (options.team) {
    const wanted = String(options.team).toLowerCase();
    const exact = buildManifest(teams).filter((row) => {
      const isMatch = row.slug === wanted || row.team.toLowerCase() === wanted;
      return isMatch && fs.existsSync(path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_logo_square.png`));
    });
    rows.length = 0;
    rows.push(...exact);
  }

  if (!rows.length) {
    console.log('No existing logo_square files matched for normalization.');
    return;
  }

  const summary = [];
  for (const row of rows) {
    const finalPath = path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_logo_square.png`);
    const tmpPath = path.join(os.tmpdir(), `${row.slug}_logo_square_normalize.png`);
    fs.copyFileSync(finalPath, tmpPath);
    normalizeLogo(tmpPath, finalPath);
    fs.unlinkSync(tmpPath);
    summary.push({ slug: row.slug, finalPath, status: 'normalized' });
    console.log(`${row.slug}: ${finalPath}`);
  }
  const target = writeJson('team-logo-normalize-summary.json', summary);
  console.log(`Summary: ${target}`);
}

async function generateLogos(teams, options = {}) {
  ensureToolAvailable('magick');
  const rows = pickTeamsForLogoGeneration(teams, options);
  if (!rows.length) {
    console.log('No teams selected for logo generation.');
    return;
  }

  const summary = [];
  for (const row of rows) {
    const rawPath = path.join(RAW_OUTPUT_DIR, `${row.slug}_logo_raw.png`);
    const finalPath = path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_logo_square.png`);
    if (options.dryRun) {
      summary.push({ slug: row.slug, finalPath, status: 'dry-run' });
      continue;
    }
    const base64 = await generateImageBase64(row.logo_prompt, options);
    const writtenRawPath = writeRawLogo(base64, row.slug);
    const writtenFinalPath = writeFinalLogo(row.slug, writtenRawPath);
    summary.push({ slug: row.slug, rawPath: writtenRawPath, finalPath: writtenFinalPath, status: 'generated' });
    console.log(`${row.slug}: ${writtenFinalPath}`);
  }

  const target = writeJson('team-logo-generation-summary.json', summary);
  console.log(`Summary: ${target}`);
}

async function generateBanners(teams, options = {}) {
  ensureToolAvailable('magick');
  const rows = pickTeamsForBannerGeneration(teams, options);
  if (!rows.length) {
    console.log('No teams selected for banner generation.');
    return;
  }

  const summary = [];
  for (const row of rows) {
    const finalPath = path.join(TEAM_IMAGE_ROOT, row.slug, `${row.slug}_banner_primary.jpg`);
    if (options.dryRun) {
      summary.push({ slug: row.slug, finalPath, status: 'dry-run' });
      continue;
    }
    const base64 = await generateImageBase64(row.banner_prompt, {
      ...options,
      size: BANNER_GENERATION_SIZE,
      background: 'opaque',
      outputFormat: 'jpeg'
    });
    const writtenRawPath = writeRawBanner(base64, row.slug);
    const writtenFinalPath = writeFinalBanner(row.slug, writtenRawPath);
    summary.push({ slug: row.slug, rawPath: writtenRawPath, finalPath: writtenFinalPath, status: 'generated' });
    console.log(`${row.slug}: ${writtenFinalPath}`);
  }

  const target = writeJson('team-banner-generation-summary.json', summary);
  console.log(`Summary: ${target}`);
}

function printUsage() {
  console.log([
    'Usage: node scripts/team_logo_pipeline.mjs <command>',
    '',
    'Commands:',
    '  audit     Print coverage summary for FrontEnd/static/images/teams',
    '  manifest  Write full team logo manifest JSON to tmp/team-logo-pipeline',
    '  prompts   Write prompt-only JSON to tmp/team-logo-pipeline',
    '  generate-banners [--limit N] [--team slug_or_name] [--force] [--dry-run] [--model MODEL]',
    `            Generate banner_primary assets at ${BANNER_TARGET_WIDTH}x${BANNER_TARGET_HEIGHT}`,
    '  normalize-existing-banners [--team slug_or_name]',
    `            Re-save existing banner_primary assets to ${BANNER_TARGET_WIDTH}x${BANNER_TARGET_HEIGHT}`,
    '  generate-logos [--limit N] [--team slug_or_name] [--force] [--dry-run] [--model MODEL]',
    `            Generate logo_square assets at ${LOGO_TARGET_WIDTH}x${LOGO_TARGET_HEIGHT}`,
    '  normalize-existing-logos [--team slug_or_name]',
    `            Re-save existing logo_square assets to ${LOGO_TARGET_WIDTH}x${LOGO_TARGET_HEIGHT}`
  ].join('\n'));
}

async function main() {
  const command = process.argv[2];
  if (!command || command === '--help' || command === '-h') {
    printUsage();
    process.exit(command ? 0 : 1);
  }

  const teams = parseTeamsFile(TEAM_FILE);
  const args = parseArgs(process.argv.slice(3));
  switch (command) {
    case 'audit':
      printAudit(teams);
      break;
    case 'manifest':
      writeManifest(teams);
      break;
    case 'prompts':
      writePrompts(teams);
      break;
    case 'generate-banners':
      await generateBanners(teams, args);
      break;
    case 'normalize-existing-banners':
      normalizeExistingBanners(teams, args);
      break;
    case 'generate-logos':
      await generateLogos(teams, args);
      break;
    case 'normalize-existing-logos':
      normalizeExistingLogos(teams, args);
      break;
    default:
      printUsage();
      process.exit(1);
  }
}

await main();
