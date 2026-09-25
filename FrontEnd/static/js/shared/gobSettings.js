/**
 * Settings panel. Opens from the auth-bar gear today and from GOBSettings.open()
 * for the future shell rail. Audio writes straight to uiSfx. Coach tiles render
 * only fields /api/auth/me already returns.
 */
import { bindGobDensity } from './gobDensity.js';
import {
  getAudioState,
  setChannelLevel,
  setChannelMuted,
  subscribeAudio,
} from './uiSfx.js';

const SPEAKER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3Z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>';
const SPEAKER_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3Z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>';

const ROWS = [
  ['master', 'Master'],
  ['music', 'Music'],
  ['sfx', 'Sound Effects'],
  ['ambience', 'Ambience'],
];

let host = null;
let open = false;
let onKey = null;
let unsubscribe = null;

function ensureCss() {
  const hrefs = ['/css/gob-tokens.css', '/css/gob-components.css', '/fonts/app-fonts.css'];
  hrefs.forEach((href) => {
    if (document.querySelector('link[data-gob-foundation="' + href + '"]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.setAttribute('data-gob-foundation', href);
    document.head.appendChild(link);
  });
  if (!document.getElementById('gob-settings-faces')) {
    const style = document.createElement('style');
    style.id = 'gob-settings-faces';
    style.textContent = [
      "@font-face{font-family:'Bebas Neue Pro';src:url('/fonts/BebasNeuePro-Regular.otf') format('opentype');font-weight:400;font-display:swap}",
      "@font-face{font-family:'Bebas Neue Pro';src:url('/fonts/BebasNeuePro-Bold.otf') format('opentype');font-weight:700;font-display:swap}",
      '.gob.gob-settings-host{position:fixed;left:0;right:0;bottom:0;top:var(--gob-bar-h,0px);width:auto;height:auto;background:transparent;overflow:visible;z-index:4000;--rail-w:0px;--top-h:0px}',
      '.gob.gob-settings-host.gob-1280,.gob.gob-settings-host.gob-1920{width:auto;height:auto}',
      '@media (prefers-reduced-motion:reduce){.gob .settings.is-closing{animation:none}}',
      '.gob .settings.is-closing{animation:setOut 160ms var(--ease-out) both}',
      '@keyframes setOut{to{transform:translateX(-24px);opacity:0}}',
    ].join('');
    document.head.appendChild(style);
  }
}

function barHeight() {
  const bar = document.getElementById('auth-bar');
  if (!bar) return 0;
  const rect = bar.getBoundingClientRect();
  return Math.max(0, Math.round(rect.bottom));
}

function isDesktop() {
  return typeof window !== 'undefined' && window.GOB_BUILD_PROFILE === 'desktop';
}

function sliderHtml(channel) {
  return '<div class="slider" data-channel="' + channel + '" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="100" aria-label="' + channel + ' volume"><i></i><b></b></div>';
}

function build() {
  ensureCss();
  host = document.createElement('div');
  host.className = 'gob gob-settings-host';
  host.id = 'gob-settings-host';
  host.hidden = true;
  const rows = ROWS.map(([id, label]) => {
    return '<div class="aud" data-aud="' + id + '">'
      + '<button type="button" class="mute" data-mute="' + id + '" aria-pressed="false" title="Mute ' + label + '">' + SPEAKER + '</button>'
      + '<span class="aud-l">' + label + '</span>'
      + sliderHtml(id)
      + '<span class="aud-v" data-val="' + id + '">100</span>'
      + '</div>';
  }).join('');
  host.innerHTML = ''
    + '<div class="set-scrim" data-settings-scrim></div>'
    + '<aside class="settings" role="dialog" aria-modal="true" aria-labelledby="gob-settings-title">'
    + '  <div class="set-h"><h2 id="gob-settings-title">Settings</h2><button type="button" class="set-x" data-settings-close title="Close (Esc)" aria-label="Close">×</button></div>'
    + '  <div class="set-b">'
    + '    <section class="set-s"><h3>Audio <span>Changes apply instantly</span></h3>' + rows + '</section>'
    + '    <section class="set-s" data-coach hidden><h3>Coach stats</h3><div class="cs-grid" data-coach-grid></div></section>'
    + '    <section class="set-s" data-account></section>'
    + '  </div>'
    + '  <div class="set-f"><span data-build></span><span class="conn" data-conn><i></i><span data-conn-label>Online</span></span></div>'
    + '</aside>';
  document.body.appendChild(host);
  bindGobDensity(host);
  host.addEventListener('click', onClick);
  host.addEventListener('keydown', onSliderKey);
  host.addEventListener('pointerdown', onPointerDown);
  unsubscribe = subscribeAudio(paintAudio);
  paintAudio(getAudioState());
}

function paintAudio(snapshot) {
  if (!host) return;
  const state = snapshot || getAudioState();
  ROWS.forEach(([id]) => {
    const row = host.querySelector('[data-aud="' + id + '"]');
    const slot = state[id];
    if (!row || !slot) return;
    row.classList.toggle('is-muted', !!slot.muted);
    const mute = row.querySelector('[data-mute]');
    mute.classList.toggle('on', !!slot.muted);
    mute.setAttribute('aria-pressed', slot.muted ? 'true' : 'false');
    mute.innerHTML = slot.muted ? SPEAKER_OFF : SPEAKER;
    mute.title = (slot.muted ? 'Unmute ' : 'Mute ') + row.querySelector('.aud-l').textContent;
    const slider = row.querySelector('.slider');
    slider.setAttribute('aria-valuenow', String(slot.level));
    slider.querySelector('i').style.width = slot.level + '%';
    slider.querySelector('b').style.left = slot.level + '%';
    row.querySelector('[data-val]').textContent = String(slot.level);
  });
}

function levelFromPointer(slider, event) {
  const rect = slider.getBoundingClientRect();
  const width = rect.width || 1;
  const x = Math.min(Math.max(0, event.clientX - rect.left), width);
  return Math.round((x / width) * 100);
}

function onPointerDown(event) {
  const slider = event.target.closest && event.target.closest('.slider');
  if (!slider || !host.contains(slider)) return;
  event.preventDefault();
  slider.classList.add('is-drag');
  const channel = slider.getAttribute('data-channel');
  const move = (ev) => setChannelLevel(channel, levelFromPointer(slider, ev));
  const up = () => {
    slider.classList.remove('is-drag');
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
  };
  move(event);
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

function onSliderKey(event) {
  const slider = event.target.closest && event.target.closest('.slider');
  if (!slider) return;
  const channel = slider.getAttribute('data-channel');
  const now = Number(slider.getAttribute('aria-valuenow') || 0);
  const step = event.shiftKey ? 10 : 5;
  let next = null;
  if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next = now + step;
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next = now - step;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = 100;
  if (next == null) return;
  event.preventDefault();
  setChannelLevel(channel, next);
}

function onClick(event) {
  if (event.target.closest('[data-settings-close]') || event.target.closest('[data-settings-scrim]')) {
    close();
    return;
  }
  const mute = event.target.closest('[data-mute]');
  if (mute) {
    const id = mute.getAttribute('data-mute');
    const slot = getAudioState()[id];
    setChannelMuted(id, !(slot && slot.muted));
    return;
  }
  const logout = event.target.closest('[data-settings-logout]');
  if (logout) logOut();
}

function logOut() {
  try {
    if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.buildUrl === 'function') {
      fetch(API_CONFIG.buildUrl('/api/auth/logout'), { method: 'POST' }).catch(function () {});
    }
  } catch (_err) { /* ignore */ }
  try {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
  } catch (_err) { /* ignore */ }
  window.location.href = '/mode-select.html';
}

function titleCount(champs) {
  if (!champs || typeof champs !== 'object') return null;
  return ['conf_rs', 'conf_t', 'region', 'national'].reduce((sum, key) => {
    const n = Number(champs[key]);
    return sum + (Number.isFinite(n) ? n : 0);
  }, 0);
}

function paintCoach(me) {
  const section = host.querySelector('[data-coach]');
  const grid = host.querySelector('[data-coach-grid]');
  const tiles = [];
  const record = me && me.record;
  if (record && Number.isFinite(Number(record.wins)) && Number.isFinite(Number(record.losses))) {
    tiles.push('<div class="cs"><b>' + Number(record.wins) + '\u2013' + Number(record.losses) + '</b><span>Career record</span></div>');
  }
  const titles = titleCount(me && me.championships_total);
  if (titles != null && me && me.championships_total) {
    tiles.push('<div class="cs"><b>' + titles + '</b><span>Titles</span></div>');
  }
  if (!tiles.length) {
    section.hidden = true;
    grid.innerHTML = '';
    return;
  }
  section.hidden = false;
  grid.innerHTML = tiles.join('');
}

function paintAccount(me) {
  const section = host.querySelector('[data-account]');
  const offline = isDesktop();
  const conn = host.querySelector('[data-conn]');
  const label = host.querySelector('[data-conn-label]');
  conn.classList.toggle('off', offline);
  label.textContent = offline ? 'Offline' : 'Online';
  const build = host.querySelector('[data-build]');
  const stamped = typeof window.GOB_BUILD_LABEL === 'string' ? window.GOB_BUILD_LABEL.trim() : '';
  build.textContent = stamped;
  if (offline) {
    section.innerHTML = '<h3>Account</h3><p class="set-note">Playing offline. Account settings return when you\'re back online.</p>';
    return;
  }
  const username = (me && me.username) || 'Coach';
  const email = (me && me.email) || '';
  section.innerHTML = '<h3>Account</h3>'
    + '<div class="acct"><span>Username</span><b>' + escapeText(username) + '</b><span>Email</span><b>' + escapeText(email) + '</b></div>'
    + '<a class="lnk" href="/account.html">Account details</a>'
    + '<button type="button" class="btn-ghost" data-settings-logout style="margin-top:6px">Log Out</button>';
}

function escapeText(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function loadIdentity() {
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem('auth_user') || 'null'); } catch (_err) { stored = null; }
  paintAccount(stored);
  paintCoach(null);
  if (isDesktop()) return;
  if (typeof API_CONFIG === 'undefined' || typeof API_CONFIG.buildUrl !== 'function') return;
  const headers = typeof API_CONFIG.getAuthHeaders === 'function' ? API_CONFIG.getAuthHeaders() : {};
  fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: headers })
    .then((res) => (res.ok ? res.json() : null))
    .then((me) => {
      if (!me || !open) return;
      paintAccount(me);
      paintCoach(me);
    })
    .catch(() => {});
}

function onEscape(event) {
  if (event.key === 'Escape') close();
}

export function isOpen() {
  return open;
}

export function openSettings() {
  if (!host) build();
  host.hidden = false;
  host.style.setProperty('--gob-bar-h', barHeight() + 'px');
  open = true;
  loadIdentity();
  paintAudio(getAudioState());
  if (!onKey) {
    onKey = onEscape;
    document.addEventListener('keydown', onKey);
  }
  const gear = document.getElementById('auth-settings-btn');
  if (gear) gear.setAttribute('aria-expanded', 'true');
}

export function close() {
  if (!host || !open) return;
  open = false;
  const panel = host.querySelector('.settings');
  const finish = () => {
    if (open) return;
    host.hidden = true;
    if (panel) panel.classList.remove('is-closing');
  };
  if (panel && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    panel.classList.add('is-closing');
    window.setTimeout(finish, 170);
  } else {
    finish();
  }
  if (onKey) {
    document.removeEventListener('keydown', onKey);
    onKey = null;
  }
  const gear = document.getElementById('auth-settings-btn');
  if (gear) gear.setAttribute('aria-expanded', 'false');
}

export function toggle() {
  if (open) close();
  else openSettings();
}

if (typeof window !== 'undefined') {
  window.GOBSettings = { open: openSettings, close, toggle, isOpen };
}
