/**
 * Resolves the per-team Sammy portrait path used in the FTE v2 tutorial flow.
 *
 * Assets live at /images/coaches/<abbr>/Sammy-<abbr>.png. The 8 tutorial teams
 * map to abbreviation folders below. Falls back to the generic Sammy when no
 * team is provided (Persona Intro step) or when the team isn't in the map.
 */

const TEAM_COACH_ABBR = {
  'Bentley-Truman': 'BT',
  'Four Corners': 'FC',
  'Lancaster': 'Lan',
  'Little York': 'LY',
  'Morristown': 'Mor',
  'Ocean City': 'OC',
  'South Lancaster': 'SL',
  'Xavien': 'Xav',
};

const GENERIC_SAMMY = '/images/sammy_tutorial.png';

export function getTeamSammyImage(teamName) {
  if (!teamName) return GENERIC_SAMMY;
  const abbr = TEAM_COACH_ABBR[teamName];
  if (!abbr) return GENERIC_SAMMY;
  return `/images/coaches/${abbr}/Sammy-${abbr}.png`;
}

export const GENERIC_SAMMY_IMAGE = GENERIC_SAMMY;
