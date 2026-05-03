// Coaching Grid JavaScript
// Maps command score (0-100) and momentum (0-10) to grid positions

/**
 * Convert command score (0-100) to Y coordinate percentage
 * 0 = bottom (100%), 100 = top (0%)
 * Midpoint (50) = center (50%)
 */
function commandScoreToY(commandScore) {
  // Invert: higher command score = higher on grid (lower Y percentage)
  return 100 - commandScore;
}

/**
 * Convert momentum value (0-10) to X coordinate percentage
 * 0 = left (0%), 10 = right (100%)
 * Midpoint (5) = center (50%)
 */
function momentumToX(momentum) {
  // Scale 0-10 to 0-100
  return (momentum / 10) * 100;
}

/**
 * Position all archetype dots on the grid
 */
function positionDots() {
  const dots = document.querySelectorAll('.archetype-dot');
  
  dots.forEach(dot => {
    const commandScore = parseFloat(dot.dataset.command);
    const momentum = parseFloat(dot.dataset.momentum);
    
    // Convert to percentages
    const xPercent = momentumToX(momentum);
    const yPercent = commandScoreToY(commandScore);
    
    // Position the dot
    dot.style.left = `${xPercent}%`;
    dot.style.top = `${yPercent}%`;
    
    console.log(`Positioned ${dot.dataset.archetype}: command=${commandScore}, momentum=${momentum} -> (${xPercent}%, ${yPercent}%)`);
  });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  positionDots();
  console.log('✅ Coaching Grid initialized');
});

