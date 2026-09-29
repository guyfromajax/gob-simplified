import { ensureCss, loadScript, ensureFranchiseMode } from './prepEmbed.js';
import { init as initPlan } from '/game-plan.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/gob-toast.css',
  '/game-plan.css'
];

var DEPS = [
  '/js/shared/errorHandler.js',
  '/js/shared/stateTelemetry.js',
  '/js/shared/pointerValidation.js',
  '/js/shared/playbookTeamId.js',
  '/js/shared/timeoutNavigationHelper.js',
  '/js/shared/gobToast.js',
  '/js/shared/gobLeaveConfirm.js',
  '/js/shared/attributeTooltips.js'
];

function placePlanTools(slot) {
  var row = document.querySelector('#game-plan-view .button-container')
    || document.querySelector('.button-container');
  if (!row) return;
  row.setAttribute('data-tool-home', '#game-plan-tools-home');
  slot.appendChild(row);
}

function loadGameStore() {
  if (window.__gameStoreLoaded) return Promise.resolve();
  return import('/js/state/gameStore.js').then(function () {
    window.__gameStoreLoaded = true;
  });
}

function optionsFrom(ctx) {
  var bag;
  try { bag = new URLSearchParams(window.location.search); }
  catch (err) { bag = new URLSearchParams(); }
  return {
    mode: bag.get('mode') || 'franchise',
    franchiseId: (ctx && ctx.franchiseId) || bag.get('franchise_id') || '',
    teamId: (ctx && ctx.teamId) || bag.get('team_id') || '',
    week: bag.get('week') || '',
    from: bag.get('from') || 'command_center',
    game_id: bag.get('game_id') || ''
  };
}

function loadDeps() {
  return DEPS.reduce(function (chain, src) {
    return chain.then(function () { return loadScript(src); });
  }, Promise.resolve()).then(loadGameStore);
}

export function mount(host, ctx) {
  CSS.forEach(ensureCss);
  ensureFranchiseMode();
  if (!host.querySelector('#game-plan-tools-home')) {
    var park = document.createElement('div');
    park.id = 'game-plan-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  return loadDeps().then(function () {
    host.querySelectorAll('.gob-view-skel').forEach(function (node) { node.remove(); });
    return initPlan(host, optionsFrom(ctx));
  }).then(function (api) {
    if (window.GOBTables && window.GOBTables.registerTools) {
      window.GOBTables.registerTools('game-plan-view', placePlanTools);
    }
    if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
    return {
      revalidate: function (next) {
        if (api && api.revalidate) return api.revalidate(next);
        if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
      },
      unmount: function () {
        if (api && api.unmount) api.unmount();
      }
    };
  });
}
