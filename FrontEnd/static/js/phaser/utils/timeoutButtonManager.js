/**
 * Timeout Button Manager
 * Modular timeout button functionality with feature flag
 * 
 * Features:
 * - 2-second pause during BIP/SIP turns
 * - Progress bar countdown
 * - Button state management (live/dead)
 * - Integration with animation flow
 */

// ✅ FEATURE FLAG: Set to false to completely disable timeout button functionality
export const ENABLE_TIMEOUT_BUTTON = true;

// State tracking
let buttonInitialized = false;
let pauseStartTime = null;
let pauseDuration = 2000; // 2 seconds
let playersPositioned = false;
let inboundPassStarted = false;

/**
 * Initialize the timeout button
 */
export function initTimeoutButton() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button) {
        console.warn('⚠️ [TIMEOUT STATE] Button not found');
        return;
    }
    
    button.addEventListener('click', handleTimeoutButtonClick);
    buttonInitialized = true;
    resetTimeoutButton();
}

/**
 * Ensure button is initialized (lazy initialization)
 */
function ensureButtonInitialized() {
    if (!buttonInitialized && ENABLE_TIMEOUT_BUTTON) {
        initTimeoutButton();
    }
}

/**
 * Update button state (live/dead)
 */
export function updateTimeoutButtonState(isLive, reason = '') {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    ensureButtonInitialized();
    
    const button = document.getElementById('timeout-btn');
    if (!button) {
        return;
    }
    
    button.disabled = !isLive;
    button.style.opacity = isLive ? '1' : '0.3';
    button.style.cursor = isLive ? 'pointer' : 'not-allowed';
    button.title = isLive ? 'Call Timeout' : (reason || 'Timeout not available');
}

/**
 * Check if timeout is eligible for current turn
 */
export function checkTimeoutEligibility(scene, turnData) {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return false;
    }
    
    ensureButtonInitialized();
    
    const currentTurn = turnData?.current_turn || turnData?.result_type;
    const isEligible = currentTurn === 'SIDE_INBOUND' || currentTurn === 'BASELINE_INBOUND';
    
    // Check if team has timeouts remaining (would need to check from game state)
    // For now, assume eligible if it's a BIP/SIP turn
    
    return isEligible;
}

/**
 * Start the 2-second pause
 * Returns a promise that resolves after 2 seconds
 */
export function startTimeoutPause(scene) {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return Promise.resolve();
    }
    
    ensureButtonInitialized();
    
    const isEligible = checkTimeoutEligibility(scene, scene.currentTurnData || {});
    if (!isEligible) {
        return Promise.resolve();
    }
    
    pauseStartTime = Date.now();
    playersPositioned = false;
    inboundPassStarted = false;
    
    // Make button live immediately
    updateTimeoutButtonState(true, 'Timeout available');
    
    // Show and start progress bar
    showProgressBar();
    startProgressBarAnimation();
    
    // Return promise that resolves after pause duration
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve();
        }, pauseDuration);
    });
}

/**
 * Mark that players have reached their positions
 */
export function markPlayersPositioned() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    playersPositioned = true;
    
    // If 2 seconds have elapsed, ensure button is live
    if (pauseStartTime && Date.now() - pauseStartTime >= pauseDuration) {
        updateTimeoutButtonState(true, 'Timeout available');
    }
}

/**
 * Mark that inbound pass has started
 */
export function markInboundPassStarted() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    inboundPassStarted = true;
    updateTimeoutButtonState(false, 'Inbound pass in progress');
    hideProgressBar();
}

/**
 * Reset timeout button state
 */
export function resetTimeoutButton() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    ensureButtonInitialized();
    
    pauseStartTime = null;
    playersPositioned = false;
    inboundPassStarted = false;
    
    updateTimeoutButtonState(false, 'Timeout not available');
    hideProgressBar();
}

/**
 * Handle timeout button click
 */
async function handleTimeoutButtonClick() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button || button.disabled) {
        return;
    }
    
    // Get game context from scene (would need to be passed or accessed)
    // For now, we'll need to get this from the current game scene
    const scene = window.currentGameScene; // This would need to be set by gameScene.js
    
    if (!scene) {
        console.error('❌ TIMEOUT: Cannot access game scene');
        return;
    }
    
    // Get game ID and team info from scene
    const gameId = scene.gameId || scene.simData?.game_id;
    // ✅ TIMEOUT: Use scene.userTeamSide (set in init()) or fallback to URL param
    // scene.userTeamSide is the authoritative source (set from bootGame.js data.userTeamSide)
    // URL param 'my_team' is the fallback (set when navigating to court.html)
    const urlParams = new URLSearchParams(window.location.search);
    const myTeamSide = scene.userTeamSide || urlParams.get('my_team');
    
    // Log for debugging
    console.log('⏸️ TIMEOUT: Determining calling team', {
      sceneUserTeamSide: scene.userTeamSide,
      urlParamMyTeam: urlParams.get('my_team'),
      simDataUserTeamSide: scene.simData?.user_team_side,
      finalMyTeamSide: myTeamSide
    });
    
    if (!myTeamSide) {
        console.error('❌ TIMEOUT: Cannot determine user team side (myTeamSide is undefined)');
        alert('Cannot determine your team for this game. Please return and relaunch.');
        return;
    }
    
    if (!gameId) {
        console.error('❌ TIMEOUT: Cannot determine game ID');
        return;
    }
    
    try {
        // Call timeout API
        const response = await fetch('/api/call-timeout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                game_id: gameId,
                calling_team: myTeamSide,
            }),
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error('❌ TIMEOUT: API error', error);
            alert(error.detail || 'Failed to call timeout');
            return;
        }
        
        const result = await response.json();
        console.log('✅ TIMEOUT: Called successfully', result);
        
        // Navigate to lineup screen (will be handled by timeout popup)
        // For now, we'll show a popup and navigate
        await showTimeoutPopup(result, gameId, scene);
        
    } catch (error) {
        console.error('❌ TIMEOUT: Error calling timeout', error);
        alert('Failed to call timeout. Please try again.');
    }
}

/**
 * Show timeout popup and navigate to lineup screen
 */
async function showTimeoutPopup(timeoutResult, gameId, scene) {
    // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
    // Use global helper (works in both regular scripts and modules)
    const helper = window.TimeoutNavigationHelper;
    if (!helper) {
        console.error('❌ [TIMEOUT-BUTTON] TimeoutNavigationHelper not loaded!');
        return;
    }
    
    // Get team info from scene - try multiple sources
    const homeTeam = scene.simData?.home_team?.name || 
                     scene.simData?.home_team_id || 
                     (typeof scene.homeTeam === 'string' ? scene.homeTeam : scene.homeTeam?.name) ||
                     scene.simData?.homeTeam?.name;
    const awayTeam = scene.simData?.away_team?.name || 
                     scene.simData?.away_team_id || 
                     (typeof scene.awayTeam === 'string' ? scene.awayTeam : scene.awayTeam?.name) ||
                     scene.simData?.awayTeam?.name;
    const myTeamSide = scene.userTeamSide || 
                       scene.myTeamSide || 
                       (scene.simData?.user_team_side === 'home' ? 'home' : 'away');
    
    // Fallback: Get from URL params if scene doesn't have it
    const urlParams = new URLSearchParams(window.location.search);
    const homeTeamFallback = urlParams.get('home');
    const awayTeamFallback = urlParams.get('away');
    const myTeamSideFallback = urlParams.get('my_team');
    const homeId = urlParams.get('home_id');
    const awayId = urlParams.get('away_id');
    const userTeamIdParam = urlParams.get('user_team_id');
    const franchiseId = urlParams.get('franchise_id');
    const weekParam = urlParams.get('week');
    const tournamentId = urlParams.get('tournament_id');
    const modeParam = urlParams.get('mode') || 'single';
    
    const currentQuarter = scene.simData?.quarter || scene.quarter || 1;
    
    // Build lineup object from scene
    const homeLineup = scene.homeLineup || {};
    const awayLineup = scene.awayLineup || {};
    const lineup = myTeamSide === 'home' ? homeLineup : awayLineup;
    
    // ✅ SS&S: Use unified helper to build params
    const params = buildGameNavigationParams({
        sourceParams: urlParams,
        targetQuarter: currentQuarter,
        gameId: gameId,
        resumeFromTimeout: true, // ✅ TIMEOUT: Always resuming from timeout (any quarter)
        lineup: lineup,
        myTeamSide: myTeamSide || myTeamSideFallback || 'home',
        overrides: {
            home: homeTeam || homeTeamFallback || '',
            away: awayTeam || awayTeamFallback || '',
            home_id: homeId,
            away_id: awayId,
            my_team: myTeamSide || myTeamSideFallback || 'home',
            user_team_id: userTeamIdParam,
            franchise_id: franchiseId,
            week: weekParam,
            tournament_id: tournamentId,
            mode: modeParam
        }
    });
    
    try {
        // ✅ TIMEOUT: Lineup is already included in params via helper
        // But we need to add the OTHER team's lineup (helper only adds user's team)
        const homeLineup = scene.homeLineup || {};
        const awayLineup = scene.awayLineup || {};
        
        // Add the other team's lineup params (helper only adds user's team)
        const otherTeamSide = myTeamSide === 'home' ? 'away' : 'home';
        const otherLineup = myTeamSide === 'home' ? awayLineup : homeLineup;
        ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
            const playerId = otherLineup[pos];
            if (playerId) params.set(`${otherTeamSide}_${pos.toLowerCase()}`, playerId);
        });
        
        // ✅ TIMEOUT: Fetch current game plan settings (same as quarter breaks)
        const teamId = myTeamSide === 'home' ? homeId : awayId;
        if (teamId && modeParam === 'single') {
            const gameplanParams = new URLSearchParams();
            gameplanParams.set('mode', 'single');
            gameplanParams.set('game_id', gameId);
            gameplanParams.set('team_id', teamId);
            
            const gameplanRes = await fetch(`/api/gameplan?${gameplanParams.toString()}`);
            if (gameplanRes.ok) {
                const gameplanData = await gameplanRes.json();
                // Pass game plan settings as URL param (JSON string) - same pattern as quarter breaks
                params.set('game_plan_settings', JSON.stringify(gameplanData));
            }
        }
    } catch (error) {
        console.error('❌ TIMEOUT: Error fetching lineup/game plan:', error);
        // Continue navigation even if fetch fails
    }
    
    // Navigate to lineup screen
    window.location.href = `/static/set-lineup.html?${params.toString()}`;
}

/**
 * Show progress bar
 */
function showProgressBar() {
    const wrapper = document.getElementById('timeout-progress-bar-wrapper');
    if (wrapper) {
        wrapper.style.display = 'block';
    }
}

/**
 * Hide progress bar
 */
function hideProgressBar() {
    const wrapper = document.getElementById('timeout-progress-bar-wrapper');
    if (wrapper) {
        wrapper.style.display = 'none';
    }
    const bar = document.getElementById('timeout-progress-bar');
    if (bar) {
        bar.style.width = '100%';
    }
}

/**
 * Start progress bar animation
 */
function startProgressBarAnimation() {
    const bar = document.getElementById('timeout-progress-bar');
    if (!bar) {
        return;
    }
    
    // Reset to full
    bar.style.width = '100%';
    bar.style.transition = 'none';
    
    // Start animation
    setTimeout(() => {
        bar.style.transition = `width ${pauseDuration}ms linear`;
        bar.style.width = '0%';
    }, 10);
}

/**
 * Update progress bar based on elapsed time
 */
export function updateProgressBar() {
    if (!ENABLE_TIMEOUT_BUTTON || !pauseStartTime) {
        return;
    }
    
    const elapsed = Date.now() - pauseStartTime;
    const remaining = Math.max(0, pauseDuration - elapsed);
    const percentage = (remaining / pauseDuration) * 100;
    
    const bar = document.getElementById('timeout-progress-bar');
    if (bar) {
        bar.style.width = `${percentage}%`;
    }
}

