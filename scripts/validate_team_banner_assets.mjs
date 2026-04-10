#!/usr/bin/env node

import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();
const TEAMS_FILE = path.join(ROOT, 'teams', '128_teams.txt');
const TEAM_IMAGE_ROOT = path.join(ROOT, 'FrontEnd', 'static', 'images', 'teams');

function nameToTeamSlug(teamName) {
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
      slug: nameToTeamSlug(cols[1])
    });
  }
  return teams;
}

function validate() {
  const teams = parseTeamsFile(TEAMS_FILE);
  const issues = [];

  for (const team of teams) {
    const teamDir = path.join(TEAM_IMAGE_ROOT, team.slug);
    const expected = `${team.slug}_banner_primary.jpg`;
    const expectedPath = path.join(teamDir, expected);

    if (!fs.existsSync(teamDir)) {
      issues.push({
        team: team.team,
        slug: team.slug,
        type: 'missing_dir',
        expectedPath
      });
      continue;
    }

    if (!fs.existsSync(expectedPath)) {
      const files = fs.readdirSync(teamDir).filter((f) => /banner_primary/i.test(f));
      issues.push({
        team: team.team,
        slug: team.slug,
        type: 'missing_canonical_banner',
        expectedPath,
        foundFiles: files
      });
    }
  }

  return {
    teamCount: teams.length,
    passed: issues.length === 0,
    issueCount: issues.length,
    issues
  };
}

const result = validate();
console.log(JSON.stringify(result, null, 2));
process.exit(result.passed ? 0 : 1);
