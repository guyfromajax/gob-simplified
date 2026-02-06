const { test, expect } = require('@playwright/test');

/**
 * Frontend Layout Refactor Tests
 * 
 * These tests verify the Grid-based layout refactor works correctly
 * across different viewport sizes, preventing the "court covers playcall"
 * bug that occurred on large screens (e.g., iMac).
 */

// Viewport sizes to test (matching exit criteria from refactor plan)
const VIEWPORTS = [
  { name: 'Desktop Standard', width: 1920, height: 1080 },
  { name: 'Desktop Large', width: 2560, height: 1440 },
  { name: 'Desktop iMac', width: 3840, height: 2160 }, // Original bug viewport
];

/**
 * Helper function to start the game by clicking "Play Quarter" button.
 * Handles the case where first click may do nothing (handler not attached yet).
 * Requires backend with rosters for the teams in the URL (e.g. Lancaster, Four-Corners).
 *
 * Strategy:
 * 1. Wait for button to be visible and ready (give bootGame.js time to initialize)
 * 2. Click once
 * 3. Wait for canvas attached (Phaser creates it; 'attached' is more reliable than 'visible' in headless)
 * 4. If canvas doesn't appear, try clicking button again (if it still exists)
 * 5. Wait for canvas with longer timeout
 */
async function startGame(page) {
  const playButton = page.locator('.play-button');
  await expect(playButton).toBeVisible({ timeout: 15000 });
  await page.waitForTimeout(3000); // Give bootGame.js time to attach handler and load

  await playButton.click();

  try {
    await page.waitForSelector('#phaser-container canvas', { timeout: 5000, state: 'attached' });
    return;
  } catch (e) {
    const buttonCount = await playButton.count();
    if (buttonCount > 0) {
      await page.waitForTimeout(2000);
      await playButton.click();
    }
    // Wait for canvas: use 'attached' (canvas may not be "visible" in headless due to size/rendering)
    await page.waitForSelector('#phaser-container canvas', { timeout: 45000, state: 'attached' });
  }
}

test.describe('Court Layout - Basic Structure', () => {
  test('court view loads with all major components (pre-game)', async ({ page }) => {
    await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await expect(page.locator('#scoreboard')).toBeVisible();
    await expect(page.locator('#phaser-container')).toBeAttached();
    await expect(page.locator('#playcall-center')).toBeVisible();
    await expect(page.locator('.player-stats-panel.away')).toBeVisible();
    await expect(page.locator('.player-stats-panel.home')).toBeVisible();
    await expect(page.locator('.play-button')).toBeVisible();
  });

  test('court view shows canvas after Play Quarter (requires backend rosters)', async ({ page }) => {
    await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await expect(page.locator('#scoreboard')).toBeVisible();
    await expect(page.locator('#playcall-center')).toBeVisible();
    await startGame(page);
    await expect(page.locator('#phaser-container canvas')).toBeAttached();
  });
});

test.describe('Court Layout - Viewport Stability', () => {
  for (const viewport of VIEWPORTS) {
    test(`layout stable at ${viewport.name} (${viewport.width}×${viewport.height})`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);
      await startGame(page);

      // Get bounding boxes
      const scoreboard = page.locator('#scoreboard');
      const courtContainer = page.locator('#phaser-container');
      const playcallCenter = page.locator('#playcall-center');
      
      // Verify all elements are visible
      await expect(scoreboard).toBeVisible();
      await expect(courtContainer).toBeVisible();
      await expect(playcallCenter).toBeVisible();
      
      // Get positions
      const scoreboardBox = await scoreboard.boundingBox();
      const courtBox = await courtContainer.boundingBox();
      const playcallBox = await playcallCenter.boundingBox();
      
      // Assert: Scoreboard is at top
      expect(scoreboardBox.y).toBeGreaterThanOrEqual(0);
      expect(scoreboardBox.y).toBeLessThan(150); // Should be near top (accounting for ~100px height)
      
      // Assert: Court is below scoreboard
      expect(courtBox.y).toBeGreaterThan(scoreboardBox.y + scoreboardBox.height);
      
      // Assert: Playcall center is below court (CRITICAL - this is the bug we're preventing)
      expect(playcallBox.y).toBeGreaterThan(courtBox.y + courtBox.height);
      
      // Assert: Playcall center is visible (not covered by court)
      const playcallBottom = playcallBox.y + playcallBox.height;
      const viewportHeight = viewport.height;
      expect(playcallBottom).toBeLessThanOrEqual(viewportHeight);
      
      // Assert: Playcall center has reasonable height (not collapsed)
      expect(playcallBox.height).toBeGreaterThan(100); // At least 100px tall
    });
  }
});

test.describe('Court Layout - No Overlapping Elements', () => {
  test('playcall center never overlaps court on large screens', async ({ page }) => {
    // Test the exact viewport where bug occurred
    await page.setViewportSize({ width: 3840, height: 2160 });
    await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await startGame(page);
    
    const courtContainer = page.locator('#phaser-container');
    const playcallCenter = page.locator('#playcall-center');
    
    const courtBox = await courtContainer.boundingBox();
    const playcallBox = await playcallCenter.boundingBox();
    
    // Critical assertion: Playcall must be below court (not overlapping)
    const courtBottom = courtBox.y + courtBox.height;
    expect(playcallBox.y).toBeGreaterThan(courtBottom);
    
    // Verify there's at least some gap (even if small)
    const gap = playcallBox.y - courtBottom;
    expect(gap).toBeGreaterThanOrEqual(0);
  });
  
  test('stats panels are positioned correctly', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    await startGame(page);

    const awayStats = page.locator('.player-stats-panel.away');
    const homeStats = page.locator('.player-stats-panel.home');
    const courtContainer = page.locator('#phaser-container');
    
    const awayBox = await awayStats.boundingBox();
    const homeBox = await homeStats.boundingBox();
    const courtBox = await courtContainer.boundingBox();
    
    // Assert: Away stats panel is to the left of court
    expect(awayBox.x + awayBox.width).toBeLessThanOrEqual(courtBox.x);
    
    // Assert: Home stats panel is to the right of court
    expect(homeBox.x).toBeGreaterThanOrEqual(courtBox.x + courtBox.width);
  });
});

test.describe('Court Layout - Responsive Behavior', () => {
  test('layout adapts correctly when viewport resizes', async ({ page }) => {
    // Start at standard desktop
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    await startGame(page);

    // Get initial positions
    const playcallCenter = page.locator('#playcall-center');
    const initialPlaycallBox = await playcallCenter.boundingBox();
    
    // Resize to large iMac
    await page.setViewportSize({ width: 3840, height: 2160 });
    await page.waitForTimeout(500); // Allow layout to settle
    
    // Verify playcall center is still visible and positioned correctly
    const resizedPlaycallBox = await playcallCenter.boundingBox();
    await expect(playcallCenter).toBeVisible();
    
    // Verify it's still below court
    const courtContainer = page.locator('#phaser-container');
    const courtBox = await courtContainer.boundingBox();
    expect(resizedPlaycallBox.y).toBeGreaterThan(courtBox.y + courtBox.height);
  });
});

test.describe('Court Layout - Grid Constraints', () => {
  test('playcall center respects grid-level height constraints', async ({ page }) => {
    // Test at tall viewport to verify clamp() constraint works
    await page.setViewportSize({ width: 1920, height: 2000 }); // Very tall
    await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    await startGame(page);

    const playcallCenter = page.locator('#playcall-center');
    const playcallBox = await playcallCenter.boundingBox();
    
    // Playcall should be constrained (not expand to fill all space)
    // With clamp(160px, 25vh, 300px), at 2000px height, 25vh = 500px, so max is 300px
    expect(playcallBox.height).toBeLessThanOrEqual(350); // Allow some tolerance
    expect(playcallBox.height).toBeGreaterThanOrEqual(150); // At least min height
  });
});
