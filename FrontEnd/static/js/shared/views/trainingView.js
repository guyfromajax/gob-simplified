import { ensureCss, loadScript, ensureFranchiseMode } from './viewLoader.js';
import { init as initTraining } from '/training.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/training.css',
  '/css/training-newswire.css',
  '/css/development-focus.css',
  '/css/player-development-grid.css',
  '/css/gob-toast.css'
];

var DEPS = [
  '/js/shared/trainingNewswire.js',
  '/js/shared/gobTutorialAlertResume.js',
  '/js/shared/gobToast.js',
  '/js/shared/developmentFocus.js',
  '/js/generated/trainingMatrix.js',
  '/js/utils/attributeDisplay.js',
  '/js/shared/rtBucket.js',
  '/js/shared/playerDevelopmentGrid.js'
];

var mounted = false;

function syncChrome(tab) {
  var on = tab === 'training-view';
  document.body.classList.toggle('training-page', on);
}

function placeTrainingTools() {
  // Player-dev tab has no weekly tools to park. Weekly allocation lives on
  // /training.html (focus), which owns its own header.
}

function contextValue(key) {
  var fc = window.FranchiseContext;
  if (!fc || typeof fc.get !== 'function') return '';
  try { return fc.get(key) || ''; }
  catch (err) { return ''; }
}

function optionsFrom(ctx) {
  return {
    sections: 'player-dev',
    mode: contextValue('mode') || 'franchise',
    franchiseId: (ctx && ctx.franchiseId) || contextValue('franchise_id') || '',
    teamId: (ctx && ctx.teamId) || contextValue('team_id') || '',
    week: contextValue('week') || '',
    from: contextValue('from') || 'command_center'
  };
}

function loadDeps() {
  return DEPS.reduce(function (chain, src) {
    return chain.then(function () { return loadScript(src); });
  }, Promise.resolve());
}

export function mount(host, ctx) {
  CSS.forEach(ensureCss);
  ensureFranchiseMode();
  if (!host.querySelector('#training-tools-home')) {
    var park = document.createElement('div');
    park.id = 'training-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  return loadDeps().then(function () {
    host.querySelectorAll('.gob-view-skel').forEach(function (node) { node.remove(); });
    return initTraining(host, optionsFrom(ctx));
  }).then(function (api) {
    if (window.GOBTables && window.GOBTables.registerTools) {
      window.GOBTables.registerTools('training-view', placeTrainingTools);
    }
    if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
    syncChrome('training-view');
    if (!mounted) {
      mounted = true;
      window.addEventListener('gob-tab-shown', function (evt) {
        syncChrome(evt && evt.detail && evt.detail.tab);
      });
    }
    return {
      revalidate: function (next) {
        if (api && api.revalidate) return api.revalidate(next);
        syncChrome('training-view');
        if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
      },
      unmount: function () {
        if (api && api.unmount) api.unmount();
      }
    };
  });
}
