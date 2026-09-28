import { ensureCss, loadScript, loadIsolated, embed, ensureFranchiseMode } from './prepEmbed.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/rt-buckets.css',
  '/training-report.css'
];

function placeReportTools(slot) {
  var btn = document.getElementById('locker-room-btn');
  if (!btn || btn.hidden) return;
  btn.setAttribute('data-tool-home', '#training-report-tools-home');
  slot.appendChild(btn);
}

export function mount(host) {
  CSS.forEach(ensureCss);
  if (!host.querySelector('#training-report-tools-home')) {
    var park = document.createElement('div');
    park.id = 'training-report-tools-home';
    park.hidden = true;
    host.appendChild(park);
  }
  document.body.classList.add('training-report-page');
  return embed('/training-report.html?embed=1', host, ['.training-report-container']).then(function () {
    ensureFranchiseMode();
    return loadScript('/js/shared/playerYear.js');
  }).then(function () {
    return loadIsolated('/training-report.js');
  }).then(function () {
    if (window.GOBTables && window.GOBTables.registerTools) {
      window.GOBTables.registerTools('training-report-view', placeReportTools);
    }
    if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
    if (!window.__gobTrainingReportChrome) {
      window.__gobTrainingReportChrome = true;
      window.addEventListener('gob-tab-shown', function (evt) {
        var tab = evt && evt.detail && evt.detail.tab;
        document.body.classList.toggle('training-report-page', tab === 'training-report-view');
      });
    }
    return {
      revalidate: function () {
        document.body.classList.add('training-report-page');
        if (window.GOBTables && window.GOBTables.placeTools) window.GOBTables.placeTools();
      }
    };
  });
}
