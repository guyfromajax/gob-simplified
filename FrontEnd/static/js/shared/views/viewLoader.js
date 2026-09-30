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

export function ensureFranchiseMode() {
  var ctx = window.FranchiseContext;
  if (!ctx || typeof ctx.get !== 'function' || typeof ctx.set !== 'function') return;
  if (ctx.get('mode')) return;
  var franchiseId = ctx.get('franchise_id');
  if (franchiseId) ctx.set('mode', 'franchise');
}
