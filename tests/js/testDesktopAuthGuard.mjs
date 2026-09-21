/**
 * Desktop profile must skip the login redirect. Web stays token-gated.
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const SRC = fs.readFileSync(
  path.join(ROOT, 'FrontEnd/static/js/shared/authGuard.js'),
  'utf8',
);

function runGuard({ profile, token, pathname }) {
  const replaces = [];
  const head = {
    appendChild() {},
  };
  const document = {
    head,
    getElementById() { return null; },
    getElementsByTagName() { return [head]; },
    createElement() {
      return { setAttribute() {}, appendChild() {} };
    },
  };
  const localStorage = {
    getItem(key) { return key === 'auth_token' ? (token || null) : null; },
  };
  const window = {
    GOB_BUILD_PROFILE: profile,
    location: {
      pathname: pathname || '/mode-select.html',
      search: '',
      replace(url) { replaces.push(url); },
    },
    FranchiseContext: {
      toSearchParams() { return new URLSearchParams(); },
      createParams() { return new URLSearchParams(); },
    },
  };
  vm.runInNewContext(SRC, { window, document, localStorage, encodeURIComponent });
  return replaces;
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

{
  const hops = runGuard({ profile: undefined, token: null, pathname: '/mode-select.html' });
  assert(hops.length === 1 && hops[0].indexOf('/login.html') === 0, 'web without token → login');
}

{
  const hops = runGuard({ profile: undefined, token: 'web-token', pathname: '/mode-select.html' });
  assert(hops.length === 0, 'web with token stays');
}

{
  const hops = runGuard({ profile: 'desktop', token: null, pathname: '/mode-select.html' });
  assert(hops.length === 0, 'desktop without token does not go to login');
}

{
  const hops = runGuard({ profile: 'desktop', token: null, pathname: '/franchise-command-center.html' });
  assert(hops.length === 0, 'desktop protected page does not go to login');
}

console.log('testDesktopAuthGuard.mjs ok');
