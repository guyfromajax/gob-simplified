const RECIPE_DEFINITIONS = {
  'mode-select': {
    description: 'Full Mode Select screen after authenticated home data loads',
    pathPattern: /^\/mode-select(?:\.html)?\/?$/,
    name: 'mode-select',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#around-the-league-grid',
    waitForHidden: '#mode-select-loading',
    delayMs: 750,
  },
  'around-league': {
    description: 'Around The League panel on Mode Select',
    pathPattern: /^\/mode-select(?:\.html)?\/?$/,
    name: 'around-the-league',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#around-the-league-grid',
    waitForHidden: '#mode-select-loading',
    selector: '.around-the-league-panel',
    delayMs: 750,
  },
  fcc: {
    description: 'Franchise Command Center after its shared load overlay closes',
    pathPattern: /^\/franchise-command-center(?:\.html)?\/?$/,
    name: 'franchise-command-center',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#franchise-container',
    waitForHidden: '#page-load-overlay',
    delayMs: 500,
  },
  recruiting: {
    description: 'Recruiting Hub after franchise recruiting data renders',
    pathPattern: /^\/recruiting(?:\.html)?\/?$/,
    name: 'recruiting',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#hub-root .spine-topbar',
    delayMs: 500,
  },
  'set-lineup': {
    description: 'Set Lineup after roster data renders',
    pathPattern: /^\/set-lineup(?:\.html)?\/?$/,
    name: 'set-lineup',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#roster-body tr',
    waitForHidden: '#page-load-overlay',
    delayMs: 500,
  },
  training: {
    description: 'Team Training after its points request settles',
    pathPattern: /^\/training(?:\.html)?\/?$/,
    name: 'training',
    viewport: { width: 2048, height: 1152 },
    waitFor: '#requirements-bar',
    delayMs: 1500,
  },
  'game-preview': {
    description: 'Court pre-game presentation after a valid game initializes',
    pathPattern: /^\/court(?:\.html)?\/?$/,
    name: 'game-preview',
    viewport: { width: 1920, height: 1080 },
    waitFor: '.pre-game-container:not(.hidden)',
    waitForHidden: '#page-load-overlay',
    delayMs: 500,
  },
  court: {
    description: 'Live court after Phaser and the game page finish loading',
    pathPattern: /^\/court(?:\.html)?\/?$/,
    name: 'court',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#phaser-container canvas',
    waitForHidden: '#page-load-overlay',
    delayMs: 500,
  },
  'full-game-sim': {
    description: 'Visible full-game simulation presentation on the court page',
    pathPattern: /^\/court(?:\.html)?\/?$/,
    name: 'full-game-sim',
    viewport: { width: 1920, height: 1080 },
    waitFor: '#sim-quarter-popup:not(.hidden)',
    waitForHidden: '#page-load-overlay',
    delayMs: 250,
  },
};

export const SCREENSHOT_RECIPES = Object.freeze(RECIPE_DEFINITIONS);

export function recipeNames() {
  return Object.keys(SCREENSHOT_RECIPES).sort();
}

export function getRecipe(name) {
  return SCREENSHOT_RECIPES[name] || null;
}

export function formatRecipeList() {
  return recipeNames()
    .map((name) => `  ${name.padEnd(15)} ${SCREENSHOT_RECIPES[name].description}`)
    .join('\n');
}
