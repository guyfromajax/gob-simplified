/**
 * Pre–press-conference reminder: FTE-style modal (Sammy + copy + "Got It").
 * Uses /css/fte.css (same shell as username / tutorial popups).
 */

const PGPC_SAMMY_SUPPRESS_LS_KEY = 'gob_pgpc_sammy_reminder_suppress';

const PGPC_COACH_TEAM_MAP = {
  'Four Corners': 'FC',
  'Bentley-Truman': 'BT',
  Lancaster: 'Lan',
  'Little York': 'LY',
  Morristown: 'Mor',
  'Ocean City': 'OC',
  'South Lancaster': 'SL',
  Xavien: 'Xav',
};

function ensureFteStylesheet() {
  if (document.querySelector('link[href*="fte.css"]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = '/css/fte.css';
  document.head.appendChild(link);
}

function coachSammyImageSrc(userTeamName) {
  if (!userTeamName) return '/images/sammy_tutorial.png';
  const fmt =
    typeof formatTeamName === 'function' ? formatTeamName(userTeamName) : userTeamName;
  const abbr = PGPC_COACH_TEAM_MAP[fmt];
  if (abbr) return `/images/coaches/${abbr}/Sammy-${abbr}.png`;
  return '/images/sammy_tutorial.png';
}

/** When true, skip Sammy reminder and go straight into the press conference flow. */
export function isPgpcSammyReminderSuppressed() {
  try {
    return localStorage.getItem(PGPC_SAMMY_SUPPRESS_LS_KEY) === '1';
  } catch (_) {
    return false;
  }
}

/**
 * @param {Object} opts
 * @param {string} [opts.userTeamName]
 * @param {() => void} opts.onGotIt
 */
export function showPgpcSammyReminderModal(opts) {
  const { userTeamName, onGotIt } = opts || {};
  ensureFteStylesheet();

  const backdrop = document.createElement('div');
  backdrop.id = 'pgpc-sammy-reminder-backdrop';
  backdrop.className = 'fte-username-backdrop pgpc-sammy-reminder-backdrop';
  backdrop.setAttribute('role', 'dialog');
  backdrop.setAttribute('aria-modal', 'true');
  backdrop.setAttribute('aria-labelledby', 'pgpc-sammy-reminder-title');

  const sammySrc = coachSammyImageSrc(userTeamName);

  backdrop.innerHTML = [
    '<div class="fte-modal">',
    '  <div class="fte-content">',
    `    <img src="${sammySrc}" alt="" class="fte-content-img pgpc-sammy-reminder-img" />`,
    '    <div class="fte-content-main">',
    '      <p id="pgpc-sammy-reminder-title">Hey Coach, remember to be strategic at the press conference. Your answers may impact any number of things related to the squad.</p>',
    '      <label class="pgpc-sammy-dont-show">',
    '        <input type="checkbox" id="pgpc-sammy-dont-show-again" />',
    '        <span>Don\'t show this message again</span>',
    '      </label>',
    '    </div>',
    '  </div>',
    '  <div class="fte-footer">',
    '    <button type="button" id="pgpc-sammy-reminder-gotit" class="fte-btn fte-btn-next">Got It</button>',
    '  </div>',
    '</div>',
  ].join('');

  // Styling (backdrop stacking, portrait size, "don't show" row + neutral checkbox)
  // now lives entirely in /css/fte.css — this module no longer ships its own <style>.
  document.body.appendChild(backdrop);
  requestAnimationFrame(() => {
    backdrop.classList.add('open');
  });

  const close = () => {
    backdrop.classList.remove('open');
    const rm = () => {
      try {
        backdrop.remove();
      } catch (_) {}
    };
    setTimeout(rm, 200);
  };

  const btn = backdrop.querySelector('#pgpc-sammy-reminder-gotit');
  if (btn) {
    btn.addEventListener('click', () => {
      if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
      const suppress = backdrop.querySelector('#pgpc-sammy-dont-show-again');
      if (suppress && suppress.checked) {
        try {
          localStorage.setItem(PGPC_SAMMY_SUPPRESS_LS_KEY, '1');
        } catch (_) {}
      }
      close();
      if (typeof onGotIt === 'function') onGotIt();
    });
  }
}
