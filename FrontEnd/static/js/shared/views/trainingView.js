import { ensureCss, loadScript, loadIsolated, embed, ensureFranchiseMode } from './prepEmbed.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/training.css',
  '/css/training-newswire.css',
  '/css/development-focus.css',
  '/css/player-development-grid.css'
];

var mounted = false;

function syncChrome(tab) {
  var on = tab === 'training-view';
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

export function mount(host) {
  CSS.forEach(ensureCss);
  if (!host.querySelector('#training-tools-home')) {
    var park = document.createElement('div');
    park.id = 'training-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  document.body.classList.add('training-page');
  return embed('/training.html?embed=1', host, [
    '.training-container',
    '#custom-focus-modal',
    '#auto-train-modal'
  ]).then(function () {
    var submit = host.querySelector('#submit-btn');
    if (submit) submit.remove();
    ensureFranchiseMode();
    return loadScript('/js/shared/trainingNewswire.js');
  }).then(function () {
    return loadScript('/js/shared/gobTutorialAlertResume.js');
  }).then(function () {
    return loadIsolated('/training.js');
  }).then(function () {
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
      revalidate: function () {
        syncChrome('training-view');
        if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
      }
    };
  });
}
