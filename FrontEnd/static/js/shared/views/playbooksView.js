import { ensureCss, loadScript, loadIsolated, embed, ensureFranchiseMode } from './prepEmbed.js';

var CSS = [
  '/franchise-command-center.css',
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/playbook-cmd.css',
  '/css/playbook-tiles.css',
  '/css/gob-toast.css',
  '/playbooks.css'
];

function placePlaybooksTools(slot) {
  var row = document.getElementById('playbooks-tools-row');
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

export function mount(host) {
  CSS.forEach(ensureCss);
  if (!host.querySelector('#playbooks-tools-home')) {
    var park = document.createElement('div');
    park.id = 'playbooks-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  ensureFranchiseMode();
  return embed('/playbooks.html?embed=1', host, [
    '.resource-page-container',
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
    return loadIsolated('/playbooks.js');
  }).then(function () {
    if (typeof window.initPlaybooks === 'function') return window.initPlaybooks();
  }).then(function () {
    if (window.GOBTables && window.GOBTables.registerTools) {
      window.GOBTables.registerTools('playbooks-view', placePlaybooksTools);
    }
    if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
    return {
      revalidate: function () {
        if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
      }
    };
  });
}
