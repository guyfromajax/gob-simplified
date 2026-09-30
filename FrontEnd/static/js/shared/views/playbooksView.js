import { ensureCss, loadScript, ensureFranchiseMode } from './prepEmbed.js';
import { init as initPlaybooks } from '/playbooks.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/playbook-cmd.css',
  '/css/playbook-tiles.css',
  '/css/gob-toast.css',
  '/playbooks.css'
];

var DEPS = [
  '/js/shared/errorHandler.js',
  '/js/shared/stateTelemetry.js',
  '/js/shared/pointerValidation.js',
  '/js/shared/playbookTeamId.js',
  '/js/shared/timeoutNavigationHelper.js',
  '/js/shared/gobToast.js',
  '/js/shared/gobLeaveConfirm.js'
];

function placePlaybooksTools(slot) {
  var row = document.querySelector('#playbooks-view #playbooks-tools-row')
    || document.getElementById('playbooks-tools-row');
  if (!row) return;
  row.setAttribute('data-tool-home', '#playbooks-tools-home');
  slot.appendChild(row);
}

function loadGameStore() {
  if (window.__gameStoreLoaded) return Promise.resolve();
  return import('/js/state/gameStore.js').then(function () {
    window.__gameStoreLoaded = true;
  });
}

function optionsFrom(ctx) {
  var door = window.FranchiseContext;
  function read(name) {
    return door && typeof door.get === 'function' ? (door.get(name) || '') : '';
  }
  return {
    mode: read('mode') || 'franchise',
    franchiseId: (ctx && ctx.franchiseId) || read('franchise_id') || '',
    teamId: (ctx && ctx.teamId) || read('team_id') || '',
    week: read('week') || '',
    from: read('from') || 'command_center',
    game_id: read('game_id') || ''
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
  if (!host.querySelector('#playbooks-tools-home')) {
    var park = document.createElement('div');
    park.id = 'playbooks-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  return loadDeps().then(function () {
    host.querySelectorAll('.gob-view-skel').forEach(function (node) { node.remove(); });
    return initPlaybooks(host, optionsFrom(ctx));
  }).then(function (api) {
    if (window.GOBTables && window.GOBTables.registerTools) {
      window.GOBTables.registerTools('playbooks-view', placePlaybooksTools);
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
