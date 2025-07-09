export function gridToPixels(x, y, width = 1229, height = 768) {
    const pixelX = (x / 100) * width;
    const pixelY = ((50 - y) / 50) * height;
    return { x: pixelX, y: pixelY };
  }  