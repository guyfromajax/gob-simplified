import { ensureCss, loadScript } from './viewLoader.js';
import { init as initReport } from '/training-report.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/rt-buckets.css',
  '/training-report.css'
];

var DEPS = [
  '/common.js',
  '/js/shared/playerYear.js',
  '/js/shared/scoutingReport.js',
  '/defense-display.js',
  '/js/shared/rtBucket.js',
  '/js/shared/teamShotThresholdScale.js',
  '/js/utils/attributeDisplay.js'
];

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
    from: contextValue('from') || '',
    origin: contextValue('origin') || ''
  };
}

function loadDeps() {
  return DEPS.reduce(function (chain, src) {
    return chain.then(function () { return loadScript(src); });
  }, Promise.resolve());
}

export function mount(host, ctx) {
  CSS.forEach(ensureCss);
  return loadDeps().then(function () {
    host.querySelectorAll('.gob-view-skel').forEach(function (node) { node.remove(); });
    return initReport(host, optionsFrom(ctx));
  });
}
