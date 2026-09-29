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
  var bag;
  try { bag = new URLSearchParams(window.location.search); }
  catch (err) { bag = new URLSearchParams(); }
  return {
    mode: bag.get('mode') || 'franchise',
    franchiseId: (ctx && ctx.franchiseId) || bag.get('franchise_id') || '',
    teamId: (ctx && ctx.teamId) || bag.get('team_id') || '',
    week: bag.get('week') || '',
    from: bag.get('from') || '',
    origin: bag.get('origin') || ''
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
