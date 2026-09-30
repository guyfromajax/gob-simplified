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
  // Tools park in .pg-tools, outside #training-view. The parked pill still
  // needs the standalone page class so its rules match the develop embed.
  document.body.classList.toggle('training-page', on);
  if (!window.GOBTraining) return;
  if (on) window.GOBTraining.syncAdvance();
  else if (window.GOBAdvance && window.GOBAdvance.clearOverride) window.GOBAdvance.clearOverride();
}

function placeTrainingTools(slot) {
  var home = '#training-tools-home';
  ['requirements-bar', 'auto-train-btn', 'training-tutorial-btn'].forEach(function (id) {
    var node = document.getElementById(id);
    if (!node) return;
    node.setAttribute('data-tool-home', home);
    slot.appendChild(node);
  });
}

function contextValue(key) {
  var fc = window.FranchiseContext;
  if (!fc || typeof fc.get !== 'function') return '';
  try { return fc.get(key) || ''; }
  catch (err) { return ''; }
}

function optionsFrom(ctx) {
  return {
    mode: contextValue('mode') || 'franchise',
    franchiseId: (ctx && ctx.franchiseId) || contextValue('franchise_id') || '',
    teamId: (ctx && ctx.teamId) || contextValue('team_id') || '',
    week: contextValue('week') || '',
    from: contextValue('from') || 'command_center'
  };
}

function prefetchScoutingOpen(ctx) {
  ensureCss('/css/prep-v2-scouting.css');
  ensureCss('/css/rt-buckets.css');
  loadScript('/js/utils/attributeDisplay.js');
  loadScript('/js/shared/scoutingReport.js');
  loadScript('/js/shared/playerYear.js');
  var fid = (ctx && ctx.franchiseId) || contextValue('franchise_id');
  var prep = window.GOBFccPrep || {};
  var ready = prep.whenReady ? Promise.resolve(prep.whenReady()) : Promise.resolve();
  import('/js/shared/views/scoutingView.js').then(function (mod) {
    return ready.then(function () {
      var opp = prep.peekUpcomingOpponent && prep.peekUpcomingOpponent();
      if (opp && opp.name) return opp;
      if (prep.resolveUpcomingOpponent) return prep.resolveUpcomingOpponent();
      return null;
    }).then(function (opp) {
      if (!mod.prefetchOpponentReport) return;
      return mod.prefetchOpponentReport(fid, opp);
    });
  }).catch(function () {});
}

function loadDeps() {
  return DEPS.reduce(function (chain, src) {
    return chain.then(function () { return loadScript(src); });
  }, Promise.resolve());
}

export function mount(host, ctx) {
  CSS.forEach(ensureCss);
  ensureFranchiseMode();
  prefetchScoutingOpen(ctx);
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
