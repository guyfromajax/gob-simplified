import { ensureCss, loadScript, loadIsolated, embed, ensureFranchiseMode } from './prepEmbed.js';

var CSS = [
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/rt-buckets.css',
  '/training-report.css'
];

export function mount(host) {
  CSS.forEach(ensureCss);
  document.body.classList.add('training-report-page');
  return embed('/training-report.html?embed=1', host, ['.training-report-container']).then(function () {
    ensureFranchiseMode();
    return loadScript('/js/shared/playerYear.js');
  }).then(function () {
    return loadIsolated('/training-report.js');
  }).then(function () {
    // Back lives on the report itself. Parking it in the sub-tab tools row hid it
    // the moment this view became a drill-in with no Prep sub-tabs to host the slot.
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
      }
    };
  });
}
