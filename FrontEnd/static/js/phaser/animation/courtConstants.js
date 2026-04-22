export const HOME_RIM_COORDS = { x: 91, y: 25 };
export const AWAY_RIM_COORDS = { x: 9, y: 25 };

/** Ball rest position after a make (matches BackEnd MADE_SHOT_SWEET_SPOT_*). */
export const MADE_SHOT_SWEET_SPOT_HOME_RIM = { x: 90, y: 25 };
export const MADE_SHOT_SWEET_SPOT_AWAY_RIM = { x: 10, y: 25 };

/** @param {boolean} isHomeTeamShooter — home offense attacks HOME_RIM (91). */
export function getMadeShotSweetSpotGrid(isHomeTeamShooter) {
  return isHomeTeamShooter ? MADE_SHOT_SWEET_SPOT_HOME_RIM : MADE_SHOT_SWEET_SPOT_AWAY_RIM;
}

export const HOME_TOP_KEY = { x: 64, y: 25 };
export const AWAY_TOP_KEY = { x: 36, y: 25 };
