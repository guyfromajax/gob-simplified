/**
 * Sound control in the playcall game-controls group, next to Pause and Timeout.
 * The scoreboard is not touched. The popover is mounted on document.body so an
 * ancestor with overflow:hidden cannot clip it. Opening it does not pause.
 * Mute all is the master channel. Music and SFX sliders follow uiSfx.
 */
import { getAudioState, setChannelLevel, setChannelMuted, subscribeAudio } from './uiSfx.js';

const SPEAKER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3Z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>';
const SPEAKER_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3Z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>';

function ensureStyle() {
  if (document.getElementById('court-audio-style')) return;
  const style = document.createElement('style');
  style.id = 'court-audio-style';
  style.textContent = [
    '#playcall-center .pcc-game .pcc-control-row,#playcall-center .pcc-game .pcc-timeout-row{display:flex;flex:1 1 0%;min-height:48px;width:100%;min-width:0;box-sizing:border-box}',
    '#playcall-center .pcc-game .pcc-control-row{flex-direction:row;align-items:stretch;gap:6px}',
    '@media (min-width:1920px){#playcall-center .pcc-game .pcc-control-row{gap:8px}}',
    '#playcall-center .pcc-game .pcc-control-row #pause-btn.pcc-pause,#playcall-center .pcc-game .pcc-timeout-row #timeout-btn.pcc-timeout{width:auto;flex:1 1 auto;min-width:0;min-height:0;height:100%;box-sizing:border-box}',
    '#playcall-center .pcc-game .pcc-timeout-row #timeout-btn.pcc-timeout{width:100%}',
    '#playcall-center .pcc-game #sound-btn.pcc-sound{position:static;margin:0;flex:0 0 auto;align-self:stretch;box-sizing:border-box;height:100%;aspect-ratio:1;width:auto;min-width:0;min-height:0;padding:0;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.16);border-radius:9px;color:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:background 0.14s,border-color 0.14s;box-shadow:none}',
    '.gob-snd-pop[hidden]{display:none !important}',
    '#playcall-center .pcc-game #sound-btn.pcc-sound:hover:not(:disabled),#playcall-center .pcc-game #sound-btn.pcc-sound.open{background:rgba(255,255,255,0.08);border-color:rgba(255,255,255,0.24)}',
    '#playcall-center .pcc-game #sound-btn.pcc-sound:disabled{opacity:0.5;cursor:not-allowed}',
    '#sound-btn .pcc-sound-icon{pointer-events:none}',
    '#sound-btn .pcc-sound-icon{display:grid;width:18px;height:18px;flex:0 0 auto}',
    '#sound-btn .pcc-sound-icon svg{width:18px;height:18px}',
    '.gob-snd-pop{position:fixed;z-index:10050;width:250px;padding:12px 14px;border-radius:12px;background:rgba(20,24,34,.98);box-shadow:0 16px 40px rgba(0,0,0,.45);display:flex;flex-direction:column;gap:10px;color:rgba(255,255,255,.87);font-family:Inter,sans-serif}',
    '.gob-snd-pop::after{content:"";position:absolute;left:var(--caret,50%);bottom:-5px;width:10px;height:10px;transform:translateX(-50%) rotate(45deg);background:rgba(20,24,34,.98)}',
    '.gob-snd-pop .snd-m{display:flex;align-items:center;justify-content:space-between;font-size:12px;font-weight:600;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,.08)}',
    '.gob-snd-pop .snd-r{display:grid;grid-template-columns:48px minmax(0,1fr) 26px;align-items:center;gap:10px;font-size:12px;font-weight:600}',
    '.gob-snd-pop .snd-r span:last-child{text-align:right;color:rgba(255,255,255,.60)}',
    '.gob-snd-pop .tgl{width:36px;height:20px;border-radius:10px;background:rgba(255,255,255,.12);position:relative;box-shadow:inset 0 0 0 1px rgba(255,255,255,.14);border:0;padding:0;cursor:pointer}',
    '.gob-snd-pop .tgl::after{content:"";position:absolute;left:3px;top:3px;width:14px;height:14px;border-radius:999px;background:#c9ccd3;transition:transform 140ms}',
    '.gob-snd-pop .tgl.on{background:#27408E}',
    '.gob-snd-pop .tgl.on::after{transform:translateX(16px);background:#fff}',
    '.gob-snd-pop .slider{position:relative;height:18px;display:flex;align-items:center;cursor:pointer}',
    '.gob-snd-pop .slider::before{content:"";position:absolute;left:0;right:0;height:4px;border-radius:2px;background:rgba(255,255,255,.10)}',
    '.gob-snd-pop .slider i{position:absolute;left:0;height:4px;border-radius:2px;background:rgba(255,255,255,.72)}',
    '.gob-snd-pop .slider b{position:absolute;width:14px;height:14px;margin-left:-7px;border-radius:999px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.5)}',
  ].join('');
  document.head.appendChild(style);
}

function controlsAreShown() {
  const pause = document.getElementById('pause-btn');
  const timeout = document.getElementById('timeout-btn');
  const shown = (el) => {
    if (!el || el.hidden) return false;
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  return shown(pause) || shown(timeout);
}

function paint(btn, pop, state) {
  const master = state.master || { muted: false, level: 100 };
  const icon = btn.querySelector('.pcc-sound-icon');
  btn.classList.toggle('is-muted', !!master.muted);
  if (icon) icon.innerHTML = master.muted ? SPEAKER_OFF : SPEAKER;
  btn.title = 'Sound';
  btn.setAttribute('aria-label', master.muted ? 'Sound (muted)' : 'Sound');
  const tgl = pop.querySelector('.tgl');
  tgl.classList.toggle('on', !!master.muted);
  tgl.setAttribute('aria-checked', master.muted ? 'true' : 'false');
  ['music', 'sfx'].forEach((id) => {
    const row = pop.querySelector('[data-aud="' + id + '"]');
    const slot = state[id] || { level: 100 };
    const slider = row.querySelector('.slider');
    slider.setAttribute('aria-valuenow', String(slot.level));
    slider.querySelector('i').style.width = slot.level + '%';
    slider.querySelector('b').style.left = slot.level + '%';
    row.querySelector('[data-val]').textContent = String(slot.level);
  });
}

function mirror(method, channel, value) {
  const api = window.GOBUiSfx;
  const local = method === 'setChannelLevel' ? setChannelLevel : setChannelMuted;
  local(channel, value);
  // Localhost serves Phaser from /static and this module from /js, so the
  // playback subscribers and this file can be two copies of uiSfx. Write both.
  if (api && api[method] && api[method] !== local) api[method](channel, value);
}

function levelFromPointer(slider, event) {
  const rect = slider.getBoundingClientRect();
  const width = rect.width || 1;
  const x = Math.min(Math.max(0, event.clientX - rect.left), width);
  return Math.round((x / width) * 100);
}

function placePopover(btn, pop) {
  const rect = btn.getBoundingClientRect();
  const width = pop.offsetWidth || 250;
  const height = pop.offsetHeight || 0;
  const gap = 8;
  let left = rect.right - width;
  left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
  let top = rect.top - height - gap;
  if (top < 8) top = 8;
  pop.style.left = Math.round(left) + 'px';
  pop.style.top = Math.round(top) + 'px';
  const caret = rect.left + rect.width / 2 - left;
  pop.style.setProperty('--caret', Math.round(caret) + 'px');
}

export function mountCourtAudio(root) {
  const host = root && root.querySelector
    ? (root.classList && root.classList.contains('pcc-zone-body')
      ? root
      : root.querySelector('.pcc-game .pcc-zone-body'))
    : null;
  const zone = host || document.querySelector('#playcall-center .pcc-game .pcc-zone-body');
  if (!zone || zone.querySelector('#sound-btn')) return;
  ensureStyle();

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.id = 'sound-btn';
  btn.className = 'pcc-sound';
  btn.title = 'Sound';
  btn.setAttribute('aria-label', 'Sound');
  btn.setAttribute('aria-expanded', 'false');
  btn.innerHTML = '<span class="pcc-sound-icon" aria-hidden="true">' + SPEAKER + '</span>';
  const row = document.createElement('div');
  row.className = 'pcc-control-row';
  const pause = zone.querySelector('#pause-btn');
  const timeout = zone.querySelector('#timeout-btn');
  if (pause) pause.before(row);
  else zone.appendChild(row);
  if (pause) row.appendChild(pause);
  row.appendChild(btn);
  if (timeout) {
    const timeoutRow = document.createElement('div');
    timeoutRow.className = 'pcc-timeout-row';
    timeout.before(timeoutRow);
    timeoutRow.appendChild(timeout);
  }

  const pop = document.createElement('div');
  pop.className = 'gob-snd-pop';
  pop.hidden = true;
  pop.innerHTML = ''
    + '<div class="snd-m"><span>Mute all</span><button type="button" class="tgl" role="switch" aria-checked="false" aria-label="Mute all"></button></div>'
    + '<div class="snd-r" data-aud="music"><span>Music</span><div class="slider" data-channel="music" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="100" aria-label="Music"><i></i><b></b></div><span data-val>100</span></div>'
    + '<div class="snd-r" data-aud="sfx"><span>SFX</span><div class="slider" data-channel="sfx" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="100" aria-label="SFX"><i></i><b></b></div><span data-val>100</span></div>';
  document.body.appendChild(pop);

  const setOpen = (next) => {
    if (next && (btn.hidden || !controlsAreShown())) return;
    pop.hidden = !next;
    btn.classList.toggle('open', next);
    btn.setAttribute('aria-expanded', next ? 'true' : 'false');
    if (next) placePopover(btn, pop);
  };

  const syncVisibility = () => {
    const show = controlsAreShown();
    btn.hidden = !show;
    if (!show) setOpen(false);
  };
  syncVisibility();

  btn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    setOpen(pop.hidden);
  });
  pop.querySelector('.tgl').addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    mirror('setChannelMuted', 'master', !getAudioState().master.muted);
  });
  pop.addEventListener('pointerdown', (event) => {
    const slider = event.target.closest && event.target.closest('.slider');
    if (!slider) return;
    event.preventDefault();
    event.stopPropagation();
    const channel = slider.getAttribute('data-channel');
    const move = (ev) => mirror('setChannelLevel', channel, levelFromPointer(slider, ev));
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    move(event);
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  pop.addEventListener('keydown', (event) => {
    const slider = event.target.closest && event.target.closest('.slider');
    if (!slider) {
      if (event.key === 'Escape') setOpen(false);
      return;
    }
    const channel = slider.getAttribute('data-channel');
    const now = Number(slider.getAttribute('aria-valuenow') || 0);
    const step = event.shiftKey ? 10 : 5;
    let next = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next = now + step;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next = now - step;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 100;
    else if (event.key === 'Escape') setOpen(false);
    if (next == null) return;
    event.preventDefault();
    mirror('setChannelLevel', channel, next);
  });
  document.addEventListener('click', (event) => {
    if (btn.contains(event.target) || pop.contains(event.target)) return;
    setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });
  const sizeSound = () => {
    const row = btn.parentElement;
    if (!row) return;
    const h = Math.round(row.getBoundingClientRect().height);
    if (!h) return;
    const px = h + 'px';
    if (btn.style.width === px) return;
    btn.style.width = px;
  };
  sizeSound();
  window.addEventListener('resize', () => {
    syncVisibility();
    sizeSound();
    if (!pop.hidden) placePopover(btn, pop);
  });
  if (typeof ResizeObserver === 'function') {
    const ro = new ResizeObserver(() => {
      sizeSound();
      if (!pop.hidden) placePopover(btn, pop);
    });
    ro.observe(row);
  }
  const watch = document.getElementById('playcall-center') || document.body;
  if (typeof MutationObserver === 'function') {
    const observer = new MutationObserver(syncVisibility);
    observer.observe(watch, { attributes: true, attributeFilter: ['style', 'class', 'hidden'], subtree: true });
  }
  subscribeAudio((state) => paint(btn, pop, state));
  paint(btn, pop, getAudioState());
}

export function mountCourtAudioWhenReady() {
  mountCourtAudio(document.getElementById('playcall-center'));
}

if (typeof window !== 'undefined') {
  window.GOBCourtAudio = { mountCourtAudio, mountCourtAudioWhenReady };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountCourtAudioWhenReady);
  } else {
    mountCourtAudioWhenReady();
  }
}
