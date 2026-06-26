let offsetX = 0;
let offsetY = 0;

export function setCourtOffsets(x = 0, y = 0) {
  offsetX = x;
  offsetY = y;
}

export function gridToPixels(x, y, width = 1229, height = 768, applyOffset = false) {
  const pixelX = (x / 100) * width + (applyOffset ? offsetX : 0);
  const pixelY = ((50 - y) / 50) * height + (applyOffset ? offsetY : 0);
  return { x: pixelX, y: pixelY };
}

export function pixelsToGrid(pixelX, pixelY, width = 1229, height = 768, applyOffset = false) {
  const sourceX = Number(pixelX) - (applyOffset ? offsetX : 0);
  const sourceY = Number(pixelY) - (applyOffset ? offsetY : 0);
  const gridX = (sourceX / width) * 100;
  const gridY = 50 - ((sourceY / height) * 50);
  return { x: gridX, y: gridY };
}
