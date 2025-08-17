export const config = {
  containerId: 'text-scroll',
  maxLines: 100,
};

export function appendToTextScroll(message, cfg = {}) {
  const {
    container = document.getElementById(config.containerId),
    maxLines = config.maxLines,
    timestampPrefix,
  } = cfg;

  if (!container) {
    return;
  }

  const atBottom = container.scrollTop + container.clientHeight === container.scrollHeight;

  const line = document.createElement('div');
  line.textContent = timestampPrefix ? `${timestampPrefix} ${message}` : message;
  container.appendChild(line);

  while (container.children.length > maxLines) {
    container.removeChild(container.firstChild);
  }

  if (atBottom) {
    container.scrollTop = container.scrollHeight - container.clientHeight;
  }

  console.log('textScroll:append', line.textContent.slice(0, 40));
}

