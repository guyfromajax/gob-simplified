/**
 * Speaker cap on the existing scoreboard. Absolute overlay only — it does not
 * add a grid column or change #scoreboard / #phaser-container size.
 * Mute all is the master channel. Music and SFX sliders follow uiSfx.
 * Opening the popover does not pause the game.
 */
import { getAudioState, setChannelLevel, setChannelMuted, subscribeAudio } from './uiSfx.js';

const SPEAKER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3Z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>';
const SPEAKER_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3Z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>';

function ensureStyle() {
  if (document.getElementById('court-audio-style')) return;
  const style = document.createElement('style');
  style.id = 'court-audio-style';
  style.textContent = [
    '#scoreboard .sb-snd{position:absolute;right:0;top:0;bottom:0;z-index:1002;display:flex;align-items:center;padding:0 8px;border-left:1px solid rgba(255,255,255,.08);pointer-events:auto}',
    '#scoreboard .sb-snd button{width:30px;height:30px;border-radius:7px;display:grid;place-items:center;color:rgba(255,255,255,.38);background:transparent;border:0;padding:0;cursor:pointer}',
    '#scoreboard .sb-snd button svg{width:17px;height:17px}',
    '#scoreboard .sb-snd button:hover,#scoreboard .sb-snd button.open{color:#fff;background:rgba(255,255,255,.08)}',
    '#scoreboard .sb-snd button.is-muted{color:rgba(255,255,255,.60)}',
    '#scoreboard .snd-pop{position:absolute;right:-6px;top:calc(100% + 8px);width:250px;padding:12px 14px;border-radius:12px;background:rgba(20,24,34,.98);box-shadow:0 16px 40px rgba(0,0,0,.45);display:flex;flex-direction:column;gap:10px;z-index:1003;color:rgba(255,255,255,.87);font-family:Inter,sans-serif}',
    '#scoreboard .snd-pop::before{content:"";position:absolute;right:16px;top:-5px;width:10px;height:10px;transform:rotate(45deg);background:rgba(20,24,34,.98)}',
    '#scoreboard .snd-m{display:flex;align-items:center;justify-content:space-between;font-size:12px;font-weight:600;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,.08)}',
    '#scoreboard .snd-r{display:grid;grid-template-columns:48px minmax(0,1fr) 26px;align-items:center;gap:10px;font-size:12px;font-weight:600}',
    '#scoreboard .snd-r span:last-child{text-align:right;color:rgba(255,255,255,.60)}',
    '#scoreboard .tgl{width:36px;height:20px;border-radius:10px;background:rgba(255,255,255,.12);position:relative;box-shadow:inset 0 0 0 1px rgba(255,255,255,.14);border:0;padding:0;cursor:pointer}',
    '#scoreboard .tgl::after{content:"";position:absolute;left:3px;top:3px;width:14px;height:14px;border-radius:999px;background:#c9ccd3;transition:transform 140ms}',
    '#scoreboard .tgl.on{background:#27408E}',
    '#scoreboard .tgl.on::after{transform:translateX(16px);background:#fff}',
    '#scoreboard .slider{position:relative;height:18px;display:flex;align-items:center;cursor:pointer}',
    '#scoreboard .slider::before{content:"";position:absolute;left:0;right:0;height:4px;border-radius:2px;background:rgba(255,255,255,.10)}',
    '#scoreboard .slider i{position:absolute;left:0;height:4px;border-radius:2px;background:rgba(255,255,255,.72)}',
    '#scoreboard .slider b{position:absolute;width:14px;height:14px;margin-left:-7px;border-radius:999px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.5)}',
  ].join('');
  document.head.appendChild(style);
}

function paint(root, state) {
  const master = state.master || { muted: false, level: 100 };
  const btn = root.querySelector('button');
  btn.classList.toggle('is-muted', !!master.muted);
  btn.innerHTML = master.muted ? SPEAKER_OFF : SPEAKER;
  btn.title = master.muted ? 'Sound (muted)' : 'Sound';
  const tgl = root.querySelector('.tgl');
  tgl.classList.toggle('on', !!master.muted);
  tgl.setAttribute('aria-checked', master.muted ? 'true' : 'false');
  ['music', 'sfx'].forEach((id) => {
    const row = root.querySelector('[data-aud="' + id + '"]');
    const slot = state[id] || { level: 100 };
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

export function mountCourtAudio(scoreboard) {
  if (!scoreboard || scoreboard.querySelector('.sb-snd')) return;
  ensureStyle();
  const cap = document.createElement('div');
  cap.className = 'sb-snd';
  cap.innerHTML = ''
    + '<button type="button" title="Sound" aria-label="Sound" aria-expanded="false">' + SPEAKER + '</button>'
    + '<div class="snd-pop" hidden>'
    + '  <div class="snd-m"><span>Mute all</span><button type="button" class="tgl" role="switch" aria-checked="false" aria-label="Mute all"></button></div>'
    + '  <div class="snd-r" data-aud="music"><span>Music</span><div class="slider" data-channel="music" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="100" aria-label="Music"><i></i><b></b></div><span data-val>100</span></div>'
    + '  <div class="snd-r" data-aud="sfx"><span>SFX</span><div class="slider" data-channel="sfx" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="100" aria-label="SFX"><i></i><b></b></div><span data-val>100</span></div>'
    + '</div>';
  scoreboard.appendChild(cap);
  const pop = cap.querySelector('.snd-pop');
  const btn = cap.querySelector('button');
  const setOpen = (next) => {
    pop.hidden = !next;
    btn.classList.toggle('open', next);
    btn.setAttribute('aria-expanded', next ? 'true' : 'false');
  };
  btn.addEventListener('click', (event) => {
    event.stopPropagation();
    setOpen(pop.hidden);
  });
  cap.querySelector('.tgl').addEventListener('click', (event) => {
    event.stopPropagation();
    const muted = !getAudioState().master.muted;
    setChannelMuted('master', muted);
  });
  cap.addEventListener('pointerdown', (event) => {
    const slider = event.target.closest && event.target.closest('.slider');
    if (!slider) return;
    event.preventDefault();
    event.stopPropagation();
    const channel = slider.getAttribute('data-channel');
    const move = (ev) => setChannelLevel(channel, levelFromPointer(slider, ev));
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    move(event);
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  cap.addEventListener('keydown', (event) => {
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
    setChannelLevel(channel, next);
  });
  document.addEventListener('click', (event) => {
    if (!cap.contains(event.target)) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });
  subscribeAudio((state) => paint(cap, state));
  paint(cap, getAudioState());
}

export function mountCourtAudioWhenReady() {
  const scoreboard = document.getElementById('scoreboard');
  if (scoreboard) mountCourtAudio(scoreboard);
}

if (typeof window !== 'undefined') {
  window.GOBCourtAudio = { mountCourtAudio, mountCourtAudioWhenReady };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountCourtAudioWhenReady);
  } else {
    mountCourtAudioWhenReady();
  }
}
