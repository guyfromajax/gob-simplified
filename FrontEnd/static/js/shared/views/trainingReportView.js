import { ensureCss, loadScript } from './prepEmbed.js';
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
    from: read('from') || '',
    origin: read('origin') || ''
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
