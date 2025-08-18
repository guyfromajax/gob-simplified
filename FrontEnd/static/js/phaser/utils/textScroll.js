export const config = {
  containerId: 'text-scroll',
  maxLines: 100,
  autoScroll: true,
  smooth: false,
  timestampPrefix: undefined,
  lineSpacing: '1em',
};

export function appendToTextScroll(message, cfg = {}) {
  if (!message) return;
  const globalCfg =
    (typeof window !== 'undefined' && window.TEXT_SCROLL_CONFIG) || {};
  const finalCfg = { ...config, ...globalCfg, ...cfg };
  const {
    containerId,
    maxLines,
    autoScroll,
    smooth,
    timestampPrefix,
  } = finalCfg;
  const container = finalCfg.container || document.getElementById(containerId);

  if (!container) {
    return;
  }

  console.debug('textScroll:append', message.slice(0, 40));

  const appendLine = () => {
    const atTop = autoScroll && container.scrollTop === 0;

    const lineText = timestampPrefix ? `${timestampPrefix} ${message}` : message;
    const firstLine = container.firstElementChild;
    if (firstLine && firstLine.textContent === lineText) {
      return;
    }

    const line = document.createElement('div');
    line.className = 'turn-line';
    line.textContent = lineText;
    line.style.marginBottom = finalCfg.lineSpacing;
    container.insertBefore(line, container.firstChild);

    while (container.children.length > maxLines) {
      container.removeChild(container.lastChild);
    }

    if (autoScroll && atTop) {
      console.debug('textScroll:autoScroll', message.length);
      requestAnimationFrame(() =>
        container.scrollTo({
          top: 0,
          behavior: smooth ? 'smooth' : 'auto',
        }),
      );
    }

    console.log('textScroll:append', line.textContent.slice(0, 40));
  };

  const heavyUpdate = container.children.length > maxLines + 20;
  if (heavyUpdate && typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(appendLine);
  } else {
    appendLine();
  }
}
