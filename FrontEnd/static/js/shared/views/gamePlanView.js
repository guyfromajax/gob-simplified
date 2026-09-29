import { ensureCss, loadScript, loadIsolated, embed, ensureFranchiseMode } from './prepEmbed.js';

var CSS = [
  '/franchise-command-center.css',
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/gob-toast.css',
  '/game-plan.css'
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

export function mount(host) {
  CSS.forEach(ensureCss);
  if (!host.querySelector('#game-plan-tools-home')) {
    var park = document.createElement('div');
    park.id = 'game-plan-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  ensureFranchiseMode();
  return embed('/game-plan.html?embed=1', host, [
    '.resource-page-container',
    '#validation-modal',
    '#toast'
  ]).then(function () {
    return loadScript('/js/shared/errorHandler.js');
  }).then(function () {
    return loadScript('/js/shared/stateTelemetry.js');
  }).then(function () {
    return loadScript('/js/shared/pointerValidation.js');
  }).then(function () {
    return loadGameStore();
  }).then(function () {
    return loadScript('/js/shared/playbookTeamId.js');
  }).then(function () {
    return loadScript('/js/shared/timeoutNavigationHelper.js');
  }).then(function () {
    return loadScript('/js/shared/gobToast.js');
  }).then(function () {
    return loadScript('/js/shared/gobLeaveConfirm.js');
  }).then(function () {
    return loadIsolated('/game-plan.js');
  }).then(function () {
    if (typeof window.initGamePlan === 'function') return window.initGamePlan();
  }).then(function () {
    if (window.GOBTables && window.GOBTables.registerTools) {
      window.GOBTables.registerTools('game-plan-view', placePlanTools);
    }
    if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
    return {
      revalidate: function () {
        if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
      }
    };
  });
}
