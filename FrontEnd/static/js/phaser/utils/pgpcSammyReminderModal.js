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
 * @param {string} [opts.userPrimaryColor] - hex for Sammy ring
 * @param {() => void} opts.onGotIt
 */
export function showPgpcSammyReminderModal(opts) {
  const { userTeamName, userPrimaryColor, onGotIt } = opts || {};
  ensureFteStylesheet();

  const backdrop = document.createElement('div');
  backdrop.id = 'pgpc-sammy-reminder-backdrop';
  backdrop.className = 'fte-username-backdrop pgpc-sammy-reminder-backdrop';
  backdrop.setAttribute('role', 'dialog');
  backdrop.setAttribute('aria-modal', 'true');
  backdrop.setAttribute('aria-labelledby', 'pgpc-sammy-reminder-title');

  const ringColor = userPrimaryColor && /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(String(userPrimaryColor).trim())
    ? String(userPrimaryColor).trim()
    : '#F79420';

  const sammySrc = coachSammyImageSrc(userTeamName);

  backdrop.innerHTML = [
    '<div class="fte-modal">',
    '  <div class="fte-content">',
    `    <img src="${sammySrc}" alt="" class="fte-content-img pgpc-sammy-reminder-img" style="border-color: ${ringColor}; box-shadow: 0 2px 8px rgba(0,0,0,0.2), 0 0 0 2px ${ringColor}33;" />`,
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

  if (!document.getElementById('pgpc-sammy-reminder-styles')) {
    const st = document.createElement('style');
    st.id = 'pgpc-sammy-reminder-styles';
    st.textContent = `
      .pgpc-sammy-reminder-backdrop {
        z-index: 10040 !important;
      }
      .pgpc-sammy-reminder-backdrop.open {
        display: flex;
      }
      .pgpc-sammy-reminder-img {
        width: 72px;
        height: 72px;
      }
      .pgpc-sammy-reminder-backdrop .pgpc-sammy-dont-show {
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        font-weight: 400;
        color: rgba(0, 0, 0, 0.45);
        cursor: pointer;
        margin-top: 14px;
        line-height: 1.3;
      }
      .pgpc-sammy-reminder-backdrop .pgpc-sammy-dont-show:hover {
        color: rgba(0, 0, 0, 0.65);
      }
      .pgpc-sammy-reminder-backdrop .pgpc-sammy-dont-show input[type="checkbox"] {
        width: 14px;
        height: 14px;
        cursor: pointer;
        accent-color: #F79420;
        flex-shrink: 0;
      }
    `;
    document.head.appendChild(st);
  }

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
