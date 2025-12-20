// Coaching Grid JavaScript
// Maps effectiveness (0-100) and momentum (0-10) to grid positions

/**
 * Convert effectiveness value (0-100) to Y coordinate percentage
 * 0 = bottom (100%), 100 = top (0%)
 * Midpoint (50) = center (50%)
 */
function effectivenessToY(effectiveness) {
  // Invert: higher effectiveness = higher on grid (lower Y percentage)
  return 100 - effectiveness;
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
    const effectiveness = parseFloat(dot.dataset.effectiveness);
    const momentum = parseFloat(dot.dataset.momentum);
    
    // Convert to percentages
    const xPercent = momentumToX(momentum);
    const yPercent = effectivenessToY(effectiveness);
    
    // Position the dot
    dot.style.left = `${xPercent}%`;
    dot.style.top = `${yPercent}%`;
    
    console.log(`Positioned ${dot.dataset.archetype}: effectiveness=${effectiveness}, momentum=${momentum} -> (${xPercent}%, ${yPercent}%)`);
  });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  positionDots();
  console.log('✅ Coaching Grid initialized');
});

