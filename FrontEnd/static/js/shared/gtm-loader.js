/**
 * Google Tag Manager loader - production only.
 * Loads GTM only when hostname is www.geekedoutbasketball.com or geekedoutbasketball.com.
 * Prevents dev/staging traffic from polluting production analytics.
 */
(function () {
  'use strict';
  var h = window.location.hostname;
  var isProduction = h === 'www.geekedoutbasketball.com' || h === 'geekedoutbasketball.com';
  if (typeof window.dataLayer === 'undefined') {
    window.dataLayer = [];
  }
  if (!isProduction) {
    return;
  }
  (function (w, d, s, l, i) {
    w[l] = w[l] || [];
    w[l].push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' });
    var f = d.getElementsByTagName(s)[0];
    var j = d.createElement(s);
    var dl = l !== 'dataLayer' ? '&l=' + l : '';
    j.async = true;
    j.src = 'https://www.googletagmanager.com/gtm.js?id=' + i + dl;
    f.parentNode.insertBefore(j, f);
  })(window, document, 'script', 'dataLayer', 'GTM-K69GQK3D');
})();
