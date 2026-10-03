/**
 * Density switch from layout.md. Only touches an element that already has .gob.
 * ≥1680×1000 → .gob-1920, otherwise .gob-1280.
 */
export function bindGobDensity(root) {
  if (!root || !root.classList || !root.classList.contains('gob')) return function () {};
  if (typeof window.matchMedia !== 'function') {
    root.classList.add('gob-1280');
    return function () {};
  }
  const mq = window.matchMedia('(min-width: 1680px) and (min-height: 1000px)');
  const apply = () => {
    const large = !!mq.matches;
    root.classList.toggle('gob-1920', large);
    root.classList.toggle('gob-1280', !large);
  };
  if (typeof mq.addEventListener === 'function') mq.addEventListener('change', apply);
  else if (typeof mq.addListener === 'function') mq.addListener(apply);
  apply();
  return apply;
}

export function bindGobDensityAll(doc) {
  const scope = doc || (typeof document !== 'undefined' ? document : null);
  if (!scope || typeof scope.querySelectorAll !== 'function') return;
  scope.querySelectorAll('.gob').forEach((root) => bindGobDensity(root));
}

if (typeof window !== 'undefined') {
  window.GOBDensity = { bindGobDensity, bindGobDensityAll };
}
