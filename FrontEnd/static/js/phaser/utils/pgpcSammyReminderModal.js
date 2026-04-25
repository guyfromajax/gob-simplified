/**
 * Pre–press-conference reminder: FTE-style modal (Sammy + copy + "Got It").
 * Uses /css/fte.css (same shell as username / tutorial popups).
 */

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
      close();
      if (typeof onGotIt === 'function') onGotIt();
    });
  }
}
