var loadedCss = {};
var loadedScripts = {};

export function ensureCss(href) {
  if (loadedCss[href]) return;
  if (document.querySelector('link[rel="stylesheet"][href="' + href + '"]')) {
    loadedCss[href] = true;
    return;
  }
  var link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = href;
  document.head.appendChild(link);
  loadedCss[href] = true;
}

export function loadScript(src) {
  if (loadedScripts[src]) return loadedScripts[src];
  loadedScripts[src] = new Promise(function (resolve, reject) {
    var existing = document.querySelector('script[src="' + src + '"]');
    if (existing) {
      resolve();
      return;
    }
    var script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.onload = function () { resolve(); };
    script.onerror = function () { reject(new Error(src)); };
    document.body.appendChild(script);
  });
  return loadedScripts[src];
}

// Page scripts (training.js, training-report.js, game-plan.js) are classic
// files with top-level const/let. The command center already owns names like
// franchiseId, so a plain script tag is rejected. Run them in an IIFE so
// their bindings stay local and anything they assign to window still lands.
export function loadIsolated(src) {
  if (loadedScripts[src]) return loadedScripts[src];
  loadedScripts[src] = fetch(src, { credentials: 'same-origin' }).then(function (res) {
    if (!res.ok) throw new Error(src);
    return res.text();
  }).then(function (code) {
    new Function(code);
    var script = document.createElement('script');
    script.setAttribute('data-gob-isolated', src);
    window.__gobIsolatedError = '';
    script.textContent = 'try{(function(){\n' + code + '\n})();}catch(e){window.__gobIsolatedError=String(e&&e.stack||e);}';
    document.body.appendChild(script);
    if (window.__gobIsolatedError) {
      var detail = window.__gobIsolatedError;
      window.__gobIsolatedError = '';
      throw new Error(src + '\n' + detail);
    }
  });
  return loadedScripts[src];
}

export function ensureFranchiseMode() {
  var ctx = window.FranchiseContext;
  if (!ctx || typeof ctx.get !== 'function' || typeof ctx.set !== 'function') return;
  if (ctx.get('mode')) return;
  var franchiseId = ctx.get('franchise_id');
  if (!franchiseId) {
    try { franchiseId = new URLSearchParams(window.location.search).get('franchise_id'); }
    catch (err) { franchiseId = ''; }
  }
  if (franchiseId) ctx.set('mode', 'franchise');
}

export function embed(url, host, selectors) {
  return fetch(url, { credentials: 'same-origin' }).then(function (res) {
    if (!res.ok) throw new Error(url);
    return res.text();
  }).then(function (html) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    host.querySelectorAll('.gob-view-skel').forEach(function (node) { node.remove(); });
    selectors.forEach(function (sel) {
      var node = doc.querySelector(sel);
      if (node) host.appendChild(document.importNode(node, true));
    });
  });
}
