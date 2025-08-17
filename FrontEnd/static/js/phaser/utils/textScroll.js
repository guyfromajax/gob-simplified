export const config = {
  containerId: 'text-scroll',
  maxLines: 100,
  autoScroll: true,
  timestampPrefix: undefined,
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
    timestampPrefix,
  } = finalCfg;
  const container = finalCfg.container || document.getElementById(containerId);

  if (!container) {
    return;
  }

  console.debug('textScroll:append', message.slice(0, 40));

  const appendLine = () => {
    const atBottom =
      autoScroll &&
      container.scrollTop + container.clientHeight === container.scrollHeight;

    const line = document.createElement('div');
    line.textContent = timestampPrefix ? `${timestampPrefix} ${message}` : message;
    container.appendChild(line);

    while (container.children.length > maxLines) {
      container.removeChild(container.firstChild);
    }

    if (autoScroll && atBottom) {
      container.scrollTop = container.scrollHeight - container.clientHeight;
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
