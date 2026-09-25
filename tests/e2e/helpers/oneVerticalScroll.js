/**
 * Fails when any element other than the page scroller has vertical overflow
 * (scrollHeight > clientHeight + 1 and overflow-y auto or scroll).
 * Dialogs, the settings host, and hidden boxes are not page scrollers.
 */
async function assertOneVerticalScroll(page) {
  const found = await page.evaluate(() => {
    const root = document.documentElement;
    const shell = root.classList.contains('gob-shell');
    const scroller = shell
      ? document.querySelector('.main')
      : document.scrollingElement;
    const skip = function (el) {
      if (!el || el === scroller || el === document.body || el === document.documentElement) return true;
      if (el.closest('.gob-settings-host, [role="dialog"], .gob-modal-overlay, .lineup-modal, .sammy-modal, .bn-overlay, .special-stats-popup, .custom-focus-modal')) return true;
      const st = getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden') return true;
      const rect = el.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return true;
      return false;
    };
    const bad = [];
    const horizontal = [];
    document.querySelectorAll('*').forEach((el) => {
      if (skip(el)) return;
      const st = getComputedStyle(el);
      const oy = st.overflowY;
      if (oy !== 'auto' && oy !== 'scroll') return;
      const extraY = el.scrollHeight - el.clientHeight;
      const extraX = el.scrollWidth - el.clientWidth;
      if (extraY <= 1) return;
      const id = el.id ? '#' + el.id : '';
      const cls = el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '';
      const name = el.tagName.toLowerCase() + id + cls;
      if (extraX > 1 && extraY <= 24) {
        horizontal.push(name + ' x+' + extraX + ' y+' + extraY);
        return;
      }
      bad.push(name + ' y+' + extraY);
    });
    return { bad: bad, horizontal: horizontal };
  });
  if (found.bad.length) {
    throw new Error('nested vertical scroll: ' + found.bad.join(', '));
  }
  return found.horizontal;
}

module.exports = { assertOneVerticalScroll };
