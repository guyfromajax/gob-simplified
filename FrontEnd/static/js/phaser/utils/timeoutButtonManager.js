/**
 * Timeout Button Manager
 * Modular timeout button functionality with feature flag
 * 
 * Features:
 * - Always-live timeout button
 * - Toggle state management (queue/cancel timeout)
 * - Highlight effect when timeout is queued
 * - Sound effect on button click
 * - Automatic timeout execution when eligible turn is reached
 */

// ✅ FEATURE FLAG: Set to false to completely disable timeout button functionality
export const ENABLE_TIMEOUT_BUTTON = true;

// State tracking
let buttonInitialized = false;
let timeoutQueued = false; // Tracks if timeout is queued (highlighted)
let timeoutSound = null; // Audio object for button click sound
let airhornSound = null; // Audio object for airhorn sound (plays when timeout executes)

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
    
    // Load sound effects (shared with computer timeout so airhorn plays in both cases)
    ensureTimeoutSounds();
    
    console.log('🔍 [TIMEOUT DEBUG] Attaching click listener to timeout button');
    button.addEventListener('click', (e) => {
        console.log('🔍 [TIMEOUT DEBUG] Timeout button clicked! Event:', e);
        handleTimeoutButtonClick(false);
    });
    buttonInitialized = true;
    console.log('🔍 [TIMEOUT DEBUG] Timeout button initialized, buttonInitialized:', buttonInitialized);
    
    // Make button always live (enabled)
    updateTimeoutButtonState(true, 'Timeout available');
}

/**
 * Load timeout sounds if not already loaded (used by both user and computer timeout so airhorn plays in both cases)
 */
function ensureTimeoutSounds() {
    if (airhornSound && timeoutSound) return;
    try {
        const API_CONFIG = window.API_CONFIG;
        const staticPath = API_CONFIG ? API_CONFIG.getStaticPath() : '/static';
        if (!timeoutSound) {
            timeoutSound = new Audio(`${staticPath}/sounds/click-beep.wav`);
            timeoutSound.volume = 0.5;
        }
        if (!airhornSound) {
            airhornSound = new Audio(`${staticPath}/sounds/Timeout - Airhorn.mp3`);
            airhornSound.volume = 0.7;
        }
    } catch (err) {
        console.warn('⚠️ [TIMEOUT] Could not load timeout sounds:', err);
    }
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
 * Update button state (manages highlight and disabled state)
 * Button is disabled when user team has 0 timeouts remaining
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
    
    // Check if user team has timeouts remaining
    const scene = window.currentGameScene;
    let userTimeoutsRemaining = null;
    
    if (scene && scene.simData) {
        const userTeamSide = scene.userTeamSide || scene.simData?.user_team_side;
        if (userTeamSide) {
            // Get timeout count from simData (same pattern as gameScene.js)
            const homeTimeouts = scene.simData?.home_team_timeouts ?? 
                                scene.simData?.timeouts?.home ?? 
                                scene.simData?.homeTeam?.timeouts;
            const awayTimeouts = scene.simData?.away_team_timeouts ?? 
                                scene.simData?.timeouts?.away ?? 
                                scene.simData?.awayTeam?.timeouts;
            
            userTimeoutsRemaining = userTeamSide === 'home' ? homeTimeouts : awayTimeouts;
        }
    }
    
    // Disable button if 0 timeouts remaining
    if (userTimeoutsRemaining !== null && userTimeoutsRemaining <= 0) {
        button.disabled = true;
        button.style.opacity = '0.5';
        button.style.cursor = 'not-allowed';
        button.title = 'No timeouts remaining';
        // Remove highlight if disabled
        updateButtonHighlight(false);
        return;
    }
    
    // Button is enabled
    button.disabled = false;
    button.style.opacity = '1';
    button.style.cursor = 'pointer';
    button.title = timeoutQueued ? 'Cancel Timeout' : 'Call Timeout';
}

/**
 * Check if user team is on offense for current turn
 * Uses scene.teamId (universal identifier) instead of computing from userTeamSide
 */
function isUserTeamOnOffense(scene, turnData) {
    if (!scene || !turnData) {
        return false;
    }
    
    // ✅ SS&S: Use scene.teamId (universal identifier) instead of computing from userTeamSide
    const userTeamId = scene.teamId;
    if (!userTeamId) {
        return false;
    }
    
    // Get possession team ID from turn data
    const possessionTeamId = turnData.possession_team_id || turnData.offense_team_id;
    if (!possessionTeamId) {
        return false;
    }
    
    // Compare possession team with user team
    return String(possessionTeamId) === String(userTeamId);
}

/**
 * Check if timeout is eligible for current turn
 * Two-step check (in order):
 * 1. Is current turn BIP or SIP? → Always eligible (regardless of offense team)
 * 2. Is current turn HCO AND previous turn was DREB AND user team is on offense? → Eligible
 * 
 * Uses `offense_team_id` as primary field (SS&S canonical), with `possession_team_id` as fallback
 * for backward compatibility.
 * 
 * @param {Object} scene - Game scene
 * @param {Object} turnData - Turn data (from scene.simData.turns or AnimationRouter)
 * @returns {boolean} - True if eligible, false otherwise
 */
export function checkTimeoutEligibility(scene, turnData) {
    console.log('🔍 [TIMEOUT DEBUG] checkTimeoutEligibility called with turnData:', {
        result_type: turnData?.result_type,
        current_turn: turnData?.current_turn,
        offense_team_id: turnData?.offense_team_id,
        possession_team_id: turnData?.possession_team_id,
        index: turnData?.index
    });
    
    if (!ENABLE_TIMEOUT_BUTTON) {
        console.log('🔍 [TIMEOUT DEBUG] ENABLE_TIMEOUT_BUTTON is false');
        return false;
    }
    
    ensureButtonInitialized();
    
    if (!scene || !turnData) {
        console.log('🔍 [TIMEOUT DEBUG] Missing scene or turnData:', { hasScene: !!scene, hasTurnData: !!turnData });
        return false;
    }
    
    // Get user team side
    const userTeamSide = scene.userTeamSide || scene.simData?.user_team_side;
    console.log('🔍 [TIMEOUT DEBUG] userTeamSide:', userTeamSide);
    if (!userTeamSide) {
        console.log('🔍 [TIMEOUT DEBUG] No userTeamSide found');
        return false;
    }
    
    // Check 1: Is current turn BIP or SIP? (Always eligible, regardless of offense team)
    const currentTurn = turnData?.current_turn || turnData?.result_type;
    console.log('🔍 [TIMEOUT DEBUG] Check 1 - currentTurn:', currentTurn);
    if (currentTurn === 'SIDE_INBOUND' || currentTurn === 'BASELINE_INBOUND') {
        console.log('🔍 [TIMEOUT DEBUG] Check 1 PASSED - BIP or SIP turn (always eligible)');
        return true;
    }
    console.log('🔍 [TIMEOUT DEBUG] Check 1 FAILED - not BIP or SIP');
    
    // Check 2: Is current turn HCO AND previous turn was MISS with DREB AND user team is on offense?
    // This covers DREB => HCO transition when user team gets the defensive rebound
    // Note: DREB is not a turn type - it's a property of a MISS turn (rebound_type: "DREB")
    // ✅ EXCLUDE: MISS/DREB turns themselves are NOT eligible (even if current_turn is HCO)
    // We want to wait for the NEXT HCO turn after DREB animation completes
    if ((turnData?.result_type === 'MISS' || turnData?.result_type === 'BLOCK') && turnData?.rebound_type === 'DREB') {
        console.log('🔍 [TIMEOUT DEBUG] Check 2 FAILED - Current turn is MISS/DREB (not eligible, wait for next HCO turn)');
        return false;
    }
    
    if (currentTurn === 'HCO' || turnData?.result_type === 'HCO') {
        console.log('🔍 [TIMEOUT DEBUG] Check 2 - Current turn is HCO, checking previous turn and offense team');
        
        // Check if previous turn was MISS with DREB
        const previousTurn = scene.previousTurnData;
        const previousResultType = previousTurn?.result_type;
        const previousReboundType = previousTurn?.rebound_type;
        const previousNextPlayType = previousTurn?.next_play_type;
        console.log('🔍 [TIMEOUT DEBUG] Previous turn:', {
            result_type: previousResultType,
            rebound_type: previousReboundType,
            next_play_type: previousNextPlayType
        });
        
        // Check if previous turn was MISS with DREB (not Fast Break)
        // DREB => HCO: previous turn is MISS with rebound_type: "DREB" and next_play_type: "HCO"
        // DREB => Fast Break: previous turn is MISS with rebound_type: "DREB" and next_play_type: "FAST_BREAK" (not eligible)
        if (previousResultType === 'MISS' && previousReboundType === 'DREB' && previousNextPlayType === 'HCO') {
            console.log('🔍 [TIMEOUT DEBUG] Previous turn was MISS with DREB => HCO, checking if user team is on offense');
            
            // Check if user team is on offense
            const offenseTeamId = turnData?.offense_team_id || turnData?.possession_team_id;
            if (!offenseTeamId) {
                console.log('🔍 [TIMEOUT DEBUG] No offense_team_id or possession_team_id found');
                return false;
            }
            
            // ✅ SS&S: Use scene.teamId (universal identifier) instead of computing from userTeamSide
            const userTeamId = scene.teamId;
            if (!userTeamId) {
                console.log('🔍 [TIMEOUT DEBUG] No scene.teamId found');
                return false;
            }
            
            console.log('🔍 [TIMEOUT DEBUG] Check 2 - userTeamId:', userTeamId, 'offenseTeamId:', offenseTeamId);
            if (String(offenseTeamId) === String(userTeamId)) {
                console.log('🔍 [TIMEOUT DEBUG] Check 2 PASSED - DREB => HCO transition with user team on offense');
                return true;
            }
            console.log('🔍 [TIMEOUT DEBUG] Check 2 FAILED - user team not on offense');
        } else {
            console.log('🔍 [TIMEOUT DEBUG] Check 2 FAILED - previous turn was not MISS with DREB => HCO', {
                was_miss: previousResultType === 'MISS',
                had_dreb: previousReboundType === 'DREB',
                was_hco: previousNextPlayType === 'HCO'
            });
        }
    } else {
        console.log('🔍 [TIMEOUT DEBUG] Check 2 FAILED - current turn is not HCO');
    }
    
    console.log('🔍 [TIMEOUT DEBUG] All checks failed - NOT eligible');
    return false;
}

/**
 * Add or remove highlight effect from timeout button
 */
function updateButtonHighlight(highlighted) {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button) {
        return;
    }
    
    if (highlighted) {
        button.classList.add('timeout-btn-highlighted');
    } else {
        button.classList.remove('timeout-btn-highlighted');
    }
}

/**
 * Reset timeout queue state (called after timeout is executed or game resets)
 */
export function resetTimeoutQueue() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    timeoutQueued = false;
    updateButtonHighlight(false);
    updateTimeoutButtonState(true, 'Timeout available');
}


/**
 * Check if timeout is queued and should be executed
 * Called at the start of each turn (before any animations)
 * ✅ SIMPLIFIED: Timeouts only execute at the start of eligible turns, never mid-turn
 * 
 * Execution conditions:
 * 1. Timeout is queued (user clicked button)
 * 2. Current turn is eligible (BIP, SIP, or HCO after DREB with user team on offense)
 * 3. User team has timeouts remaining (checked in handleTimeoutButtonClick)
 * 
 * If conditions are met, timeout executes immediately and turn processing stops.
 * If not, turn processes normally and timeout waits for next eligible turn.
 */
export async function checkAndExecuteQueuedTimeout(scene, turnData) {
    console.log('🔍 [TIMEOUT DEBUG] checkAndExecuteQueuedTimeout called');
    console.log('🔍 [TIMEOUT DEBUG] timeoutQueued:', timeoutQueued);
    
    if (!ENABLE_TIMEOUT_BUTTON || !timeoutQueued) {
        console.log('🔍 [TIMEOUT DEBUG] Not enabled or not queued, returning false');
        return false;
    }
    
    // ✅ SIMPLIFIED: Use eligibility flag set at start of turn (single source of truth)
    // This eliminates stale data issues - eligibility was determined once with fresh turnData
    const isEligible = scene.currentTurnTimeoutEligible;
    console.log('🔍 [TIMEOUT DEBUG] Current turn eligibility (from flag):', isEligible);
    
    if (!isEligible) {
        // Not eligible, don't execute - keep flag set and check again on next turn
        console.log('🔍 [TIMEOUT DEBUG] Current turn not eligible, returning false (will check next turn)');
        return false;
    }
    
    // ✅ Eligible turn detected - execute timeout immediately at start of turn
    console.log('🔍 [TIMEOUT DEBUG] Eligible turn detected, executing timeout immediately');
    console.log('⏸️ TIMEOUT: Executing at start of eligible turn');
    
    // ✅ IMMEDIATE TURN KILLING: Stop all animations before executing timeout
    // This ensures the turn stops instantly when timeout executes (before any animations play)
    console.log('⏸️ TIMEOUT: Stopping turn animations before they start');
    
    // Pause all tweens (stops all animations)
    if (scene.tweens) {
        scene.tweens.pauseAll();
        console.log('⏸️ TIMEOUT: All tweens paused');
    }
    
    // Stop animation loop
    scene.timeoutCalled = true;
    console.log('⏸️ TIMEOUT: Animation loop stopped (scene.timeoutCalled = true)');
    
    // Execute timeout immediately (call API, show popup, play sound)
    // handleTimeoutButtonClick is in the same file, so we can call it directly
    try {
        await handleTimeoutButtonClick(true); // Pass true to skip toggle (just execute)
        console.log('✅ [TIMEOUT DEBUG] Timeout executed successfully at start of eligible turn');
    } catch (error) {
        console.error('❌ TIMEOUT: Failed to execute timeout at start of eligible turn:', error);
        // Reset queue on error
        resetTimeoutQueue();
        return false;
    }
    
    // Return true to indicate timeout was executed (stop processing this turn)
    return true;
}

/**
 * Handle timeout button click
 * @param {boolean} executeOnly - If true, execute timeout without toggling state (used when eligible turn is reached)
 */
async function handleTimeoutButtonClick(executeOnly = false) {
    console.log('🔍 [TIMEOUT DEBUG] handleTimeoutButtonClick called - executeOnly:', executeOnly);
    
    if (!ENABLE_TIMEOUT_BUTTON) {
        console.log('🔍 [TIMEOUT DEBUG] ENABLE_TIMEOUT_BUTTON is false, returning');
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button) {
        console.log('🔍 [TIMEOUT DEBUG] Button not found, returning');
        return;
    }
    
    // Get game context from scene
    const scene = window.currentGameScene;
    
    if (!scene) {
        console.error('❌ TIMEOUT: Cannot access game scene');
        return;
    }
    
    console.log('🔍 [TIMEOUT DEBUG] Scene found, executeOnly:', executeOnly);
    
    // ✅ SIMPLIFIED: Button click only toggles queue state, never executes immediately
    // Timeouts only execute at the start of eligible turns (checked in checkAndExecuteQueuedTimeout)
    if (!executeOnly) {
        console.log('🔍 [TIMEOUT DEBUG] User clicked button (executeOnly=false)');
        
        // Check if user team has timeouts remaining (button state is managed by updateTimeoutButtonState)
        // Button is automatically disabled when timeouts = 0
        
        // Play sound effect
        if (timeoutSound) {
            try {
                timeoutSound.currentTime = 0; // Reset to start
                timeoutSound.play().catch(err => {
                    console.warn('⚠️ [TIMEOUT] Could not play sound:', err);
                });
            } catch (error) {
                console.warn('⚠️ [TIMEOUT] Sound play error:', error);
            }
        }
        
        // Toggle timeout queue state
        timeoutQueued = !timeoutQueued;
        
        console.log('🔍 [TIMEOUT DEBUG] Button clicked - timeoutQueued:', timeoutQueued);
        
        if (timeoutQueued) {
            updateButtonHighlight(true);
            updateTimeoutButtonState(true, 'Timeout queued - will execute at start of next eligible turn');
            console.log('⏸️ TIMEOUT: Queued - will execute at start of next eligible turn');
        } else {
            updateButtonHighlight(false);
            updateTimeoutButtonState(true, 'Timeout available');
            console.log('⏸️ TIMEOUT: Cancelled - removed from queue');
        }
        
        // ✅ SIMPLIFIED: Never execute immediately - always wait for start of next eligible turn
        // This ensures timeouts only execute at turn boundaries, never mid-turn
        return;
    }
    
    // Execute the timeout
    // Get game ID and team info from scene
    const gameId = scene.gameId || scene.simData?.game_id;
    const urlParams = new URLSearchParams(window.location.search);
    const myTeamSide = scene.userTeamSide || urlParams.get('my_team');
    
    if (!myTeamSide) {
        console.error('❌ TIMEOUT: Cannot determine user team side (myTeamSide is undefined)');
        alert('Cannot determine your team for this game. Please return and relaunch.');
        resetTimeoutQueue();
        return;
    }
    
    if (!gameId) {
        console.error('❌ TIMEOUT: Cannot determine game ID');
        resetTimeoutQueue();
        return;
    }
    
    try {
        // 🔍 DEBUG: Log current turn data before calling timeout API (for DREB => HCO bug diagnosis)
        const currentTurnData = scene.currentTurnData || scene.simData?.turns?.[scene.currentTurn] || null;
        console.log('🔍 [TIMEOUT DEBUG] handleTimeoutButtonClick() - BEFORE API call:');
        console.log('🔍 [TIMEOUT DEBUG]   - scene.currentTurn:', scene.currentTurn);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.currentTurnData?.result_type:', scene.currentTurnData?.result_type);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.currentTurnData?.current_turn:', scene.currentTurnData?.current_turn);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.currentTurnData?.offense_team_id:', scene.currentTurnData?.offense_team_id);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.currentTurnData?.next_play_type:', scene.currentTurnData?.next_play_type);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.previousTurnData?.result_type:', scene.previousTurnData?.result_type);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.previousTurnData?.rebound_type:', scene.previousTurnData?.rebound_type);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.previousTurnData?.next_play_type:', scene.previousTurnData?.next_play_type);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.previousTurnData?.offense_team_id:', scene.previousTurnData?.offense_team_id);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.userTeamSide:', scene.userTeamSide);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.simData?.home_team_id:', scene.simData?.home_team_id);
        console.log('🔍 [TIMEOUT DEBUG]   - scene.simData?.away_team_id:', scene.simData?.away_team_id);
        
        // Call timeout API
        const API_CONFIG = window.API_CONFIG;
        if (!API_CONFIG) {
            console.error('❌ TIMEOUT: API_CONFIG not available');
            resetTimeoutQueue();
            return;
        }
        const response = await fetch(API_CONFIG.buildUrl('/api/call-timeout'), {
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
            resetTimeoutQueue();
            return;
        }
        
        const result = await response.json();
        console.log('✅ TIMEOUT: Called successfully', result);
        
        // Reset queue state
        resetTimeoutQueue();
        
        // ✅ IMMEDIATE TURN KILLING: Stop all animations before showing popup
        // This ensures the turn stops instantly when timeout is called
        // User will see animation stop and popup appear immediately
        console.log('⏸️ TIMEOUT: Killing current turn animations immediately');
        
        // Pause all tweens (stops all animations)
        if (scene.tweens) {
            scene.tweens.pauseAll();
            console.log('⏸️ TIMEOUT: All tweens paused');
        }
        
        // Stop animation loop
        scene.timeoutCalled = true;
        console.log('⏸️ TIMEOUT: Animation loop stopped (scene.timeoutCalled = true)');
        
        // Play airhorn sound when timeout executes (popup appears)
        if (airhornSound) {
            try {
                airhornSound.currentTime = 0; // Reset to start
                airhornSound.play().catch(err => {
                    console.warn('⚠️ [TIMEOUT] Could not play airhorn:', err);
                });
            } catch (error) {
                console.warn('⚠️ [TIMEOUT] Airhorn play error:', error);
            }
        }
        
        // Show popup immediately (turn is already stopped)
        // User will see: animation stops → popup appears (instantaneous)
        await showUserTimeoutPopup(result, gameId, scene);
        
    } catch (error) {
        console.error('❌ TIMEOUT: Error calling timeout', error);
        alert('Failed to call timeout. Please try again.');
        resetTimeoutQueue();
    }
}

/**
 * Show user timeout popup with "Go To Timeout" button
 * Uses same styling as End of Quarter popup
 * @param {Object} timeoutResult - Timeout result object
 * @param {string} gameId - Game ID
 * @param {Object} scene - Game scene object
 */
async function showUserTimeoutPopup(timeoutResult, gameId, scene) {
    // Remove any existing popup
    const existingPopup = document.querySelector('.user-timeout-popup');
    if (existingPopup) {
        existingPopup.remove();
    }
    
    // Get user team name
    const urlParams = new URLSearchParams(window.location.search);
    const myTeamSide = scene.userTeamSide || urlParams.get('my_team');
    const homeTeamId = scene.simData?.home_team_id;
    const awayTeamId = scene.simData?.away_team_id;
    const teamsObj = scene.simData?.teams || {};
    
    const userTeamName = myTeamSide === 'home' 
        ? ((homeTeamId && teamsObj[homeTeamId]?.name) || scene.simData?.home_team?.name || scene.homeTeam?.name || 'Your Team')
        : ((awayTeamId && teamsObj[awayTeamId]?.name) || scene.simData?.away_team?.name || scene.awayTeam?.name || 'Your Team');
    
    // Create popup (matching game-completion-popup style)
    const popup = document.createElement('div');
    popup.className = 'user-timeout-popup';
    popup.innerHTML = `
        <div class="user-timeout-content">
            <h2>${userTeamName} Called Timeout</h2>
            <div class="button-container">
                <button class="timeout-button go-to-timeout-button">Go To Timeout</button>
            </div>
        </div>
    `;
    
    // Add styles if not already present
    if (!document.getElementById('user-timeout-popup-styles')) {
        const style = document.createElement('style');
        style.id = 'user-timeout-popup-styles';
        style.textContent = `
            .user-timeout-popup {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.85);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            }

            .user-timeout-content {
                background: #fff;
                border: 6px solid #c0c0c0;
                border-radius: 12px;
                padding: 40px 60px;
                display: flex;
                flex-direction: column;
                gap: 30px;
                align-items: center;
                min-width: 400px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }

            .user-timeout-content h2 {
                font-size: 36px;
                font-weight: bold;
                color: #333;
                margin: 0;
                font-family: 'Bebas Neue', sans-serif;
                letter-spacing: 2px;
            }

            .button-container {
                display: flex;
                gap: 20px;
                width: 100%;
                justify-content: center;
            }

            .timeout-button {
                padding: 15px 40px;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
                font-family: 'Inter', sans-serif;
            }

            .go-to-timeout-button {
                background: #ff9800;
                color: #fff;
            }

            .go-to-timeout-button:hover {
                background: #f57c00;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(255, 152, 0, 0.3);
            }
        `;
        document.head.appendChild(style);
    }
    
    // ✅ FIX 2: Add click handler for button - navigation only happens on explicit click
    const goToTimeoutBtn = popup.querySelector('.go-to-timeout-button');
    goToTimeoutBtn.addEventListener('click', async () => {
        if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
        console.log('🔍 [TIMEOUT DEBUG] User clicked "Go To Timeout" button');
        
        // ✅ SAFEGUARD: Set flag to indicate user explicitly clicked button
        // This prevents auto-navigation from other code paths
        scene.userTimeoutButtonClicked = true;
        
        // Remove popup BEFORE navigation (ensures guard check passes)
        popup.remove();
        
        // Clear pending timeout data from scene
        if (scene.pendingTimeoutResult) {
            delete scene.pendingTimeoutResult;
        }
        if (scene.pendingTimeoutGameId) {
            delete scene.pendingTimeoutGameId;
        }
        
        // Navigate to lineup screen - only happens when user explicitly clicks button
        // Note: computerTimeout=false (default) ensures guard check runs
        await showTimeoutPopup(timeoutResult, gameId, scene, false);
    });
    
    document.body.appendChild(popup);
    console.log('🔍 [TIMEOUT DEBUG] User timeout popup displayed, waiting for user to click button');
}

/**
 * Show timeout popup and navigate to lineup screen
 * @param {Object} timeoutResult - Timeout result object
 * @param {string} gameId - Game ID
 * @param {Object} scene - Game scene object
 * @param {boolean} [computerTimeout=false] - Whether this is a computer timeout
 * @param {string} [computerTeamName] - Name of the computer team that called timeout
 * 
 * ✅ FIX 2: For user timeouts, this should ONLY be called when user clicks "Go To Timeout" button
 * Computer timeouts can call this directly for automatic navigation
 */
export async function showTimeoutPopup(timeoutResult, gameId, scene, computerTimeout = false, computerTeamName = null) {
    console.log('🔍 [TIMEOUT DEBUG] showTimeoutPopup called', { computerTimeout, hasResult: !!timeoutResult });

    // Computer timeout: play airhorn when timeout triggers (same as user timeout), then brief delay so it’s audible before navigation
    if (computerTimeout) {
        ensureTimeoutSounds(); // Load sounds if not yet loaded (button may never have been initialized)
        if (airhornSound) {
            try {
                airhornSound.currentTime = 0;
                airhornSound.play().catch(err => {
                    console.warn('⚠️ [TIMEOUT] Could not play airhorn (computer timeout):', err);
                });
            } catch (err) {
                console.warn('⚠️ [TIMEOUT] Airhorn play error (computer timeout):', err);
            }
            await new Promise(r => setTimeout(r, 800));
        }
    }

    // ✅ FIX 2: Guard against auto-navigation for user timeouts
    // If this is a user timeout (not computer), make sure it's being called from button click
    if (!computerTimeout) {
        // ✅ SAFEGUARD 1: Check if user timeout popup is still showing (user hasn't clicked button yet)
        const userPopup = document.querySelector('.user-timeout-popup');
        if (userPopup) {
            console.warn('⚠️ [TIMEOUT] showTimeoutPopup called for user timeout but popup still showing - ignoring navigation');
            console.warn('⚠️ [TIMEOUT] This should only happen if called from outside the button click handler');
            return; // Don't navigate if popup is still showing
        }
        
        // ✅ SAFEGUARD 2: Check if user explicitly clicked the button
        // This flag is set ONLY when the user clicks "Go To Timeout" button
        if (!scene.userTimeoutButtonClicked) {
            console.warn('⚠️ [TIMEOUT] showTimeoutPopup called for user timeout but button was not clicked - ignoring navigation');
            console.warn('⚠️ [TIMEOUT] Navigation should only happen when user explicitly clicks "Go To Timeout" button');
            return; // Don't navigate if button wasn't clicked
        }
        
        // Clear the flag after checking (prevents reuse)
        delete scene.userTimeoutButtonClicked;
        
        console.log('✅ [TIMEOUT] User timeout navigation proceeding (user explicitly clicked button)');
    }
    // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
    // Use global helper (works in both regular scripts and modules)
    const helper = window.TimeoutNavigationHelper;
    if (!helper) {
        console.error('❌ [TIMEOUT-BUTTON] TimeoutNavigationHelper not loaded!');
        return;
    }
    
    // ✅ UNIFIED STRUCTURE: Get team names from unified teams object
    // Priority: 1) teams[home_team_id].name (unified structure), 2) home_team.name (backward compatibility), 3) scene fallbacks
    const homeTeamId = scene.simData?.home_team_id;
    const awayTeamId = scene.simData?.away_team_id;
    const teamsObj = scene.simData?.teams || {};
    
    const homeTeam = (homeTeamId && teamsObj[homeTeamId]?.name) ||  // ✅ Unified structure (preferred)
                     scene.simData?.home_team?.name ||                // Backward compatibility
                     (typeof scene.homeTeam === 'string' ? scene.homeTeam : scene.homeTeam?.name) ||
                     scene.simData?.homeTeam?.name ||
                     homeTeamId;  // Last resort: use ID (should log warning if we get here)
    
    const awayTeam = (awayTeamId && teamsObj[awayTeamId]?.name) ||  // ✅ Unified structure (preferred)
                     scene.simData?.away_team?.name ||                // Backward compatibility
                     (typeof scene.awayTeam === 'string' ? scene.awayTeam : scene.awayTeam?.name) ||
                     scene.simData?.awayTeam?.name ||
                     awayTeamId;  // Last resort: use ID (should log warning if we get here)
    
    // Log warning if we had to use team ID as fallback (indicates missing team name)
    if (homeTeam === homeTeamId || awayTeam === awayTeamId) {
        console.warn('⚠️ [TIMEOUT] Using team ID as team name fallback (team name not found in unified structure)', {
            homeTeamId,
            awayTeamId,
            homeTeam,
            awayTeam,
            hasTeamsObj: !!teamsObj,
            teamsObjKeys: teamsObj ? Object.keys(teamsObj) : []
        });
    }
    const myTeamSide = scene.userTeamSide || 
                       scene.myTeamSide || 
                       (scene.simData?.user_team_side === 'home' ? 'home' : 'away');
    
    // Fallback: Get from URL params if scene doesn't have it
    const urlParams = new URLSearchParams(window.location.search);
    // ✅ SINGLE GAME FIX: Ensure game_id is available for lineup URL (NG/stats load).
    // In Single Game, scene.gameId can be unset if gameStore wasn't set; court URL still has game_id.
    const gameIdToUse = gameId || urlParams.get('game_id') || null;
    const homeTeamFallback = urlParams.get('home');
    const awayTeamFallback = urlParams.get('away');
    const myTeamSideFallback = urlParams.get('my_team');
    const homeId = urlParams.get('home_id');
    const awayId = urlParams.get('away_id');
    const teamId = urlParams.get('team_id'); // ✅ SS&S: Prefer team_id (standardized)
    const userTeamIdParam = urlParams.get('user_team_id'); // Keep for backward compatibility
    const franchiseId = urlParams.get('franchise_id');
    const weekParam = urlParams.get('week');
    const tournamentId = urlParams.get('tournament_id');
    const modeParam = urlParams.get('mode') || 'single';
    
    const currentQuarter = scene.simData?.quarter || scene.quarter || 1;
    
    // ✅ TIMEOUT CLOCK: Prefer what the user sees on screen for user timeouts (avoids stale API when
    // next simulate_turn is in flight). For computer timeouts, API response is authoritative.
    let clock = null;
    if (computerTimeout) {
        // Computer timeout: use API response first (same request that triggered navigation)
        if (timeoutResult && timeoutResult.clock) {
            clock = timeoutResult.clock;
            console.log(`✅ TIMEOUT: Using clock from API response: ${clock}`);
        }
    }
    // User timeout: prefer displayed clock (DOM → simData) so lineup shows what user saw
    if (!clock) {
        const clockEl = document.getElementById('game-clock');
        if (clockEl && clockEl.textContent && clockEl.textContent.trim()) {
            clock = clockEl.textContent.trim();
            console.log(`✅ TIMEOUT: Using clock from DOM (displayed): ${clock}`);
        }
    }
    if (!clock && scene.simData?.clock) {
        clock = scene.simData.clock;
        console.log(`✅ TIMEOUT: Using clock from scene.simData: ${clock}`);
    }
    if (!clock && timeoutResult && timeoutResult.clock) {
        clock = timeoutResult.clock;
        console.log(`✅ TIMEOUT: Using clock from API response: ${clock}`);
    }
    if (!clock && scene.simData?.turns && Array.isArray(scene.simData.turns) && scene.simData.turns.length > 0) {
        const lastTurn = scene.simData.turns[scene.simData.turns.length - 1];
        clock = lastTurn?.clock || lastTurn?.game_clock || null;
        if (clock) console.log(`✅ TIMEOUT: Using clock from last turn: ${clock}`);
    }
    if (!clock) {
        clock = urlParams.get('clock') || null;
        if (clock) console.log(`✅ TIMEOUT: Using clock from URL params: ${clock}`);
    }
    if (!clock) {
        clock = '8:00';
        console.warn(`⚠️ TIMEOUT: No clock found, defaulting to ${clock}`);
    }
    
    // ✅ TIMEOUT SCORES: Pass displayed scores in URL so lineup header shows what user saw (same rationale as clock)
    let homeScore = null;
    let awayScore = null;
    const homeScoreEl = document.getElementById('home-score');
    const awayScoreEl = document.getElementById('away-score');
    if (homeScoreEl && awayScoreEl) {
        const h = homeScoreEl.textContent?.trim();
        const a = awayScoreEl.textContent?.trim();
        if (h !== undefined && h !== '' && !isNaN(Number(h))) homeScore = Number(h);
        if (a !== undefined && a !== '' && !isNaN(Number(a))) awayScore = Number(a);
    }
    if ((homeScore === null || awayScore === null) && timeoutResult) {
        if (homeScore === null && typeof timeoutResult.home_score === 'number') homeScore = timeoutResult.home_score;
        if (awayScore === null && typeof timeoutResult.away_score === 'number') awayScore = timeoutResult.away_score;
    }
    
    // Build lineup object from scene
    const homeLineup = scene.homeLineup || {};
    const awayLineup = scene.awayLineup || {};
    const lineup = myTeamSide === 'home' ? homeLineup : awayLineup;
    
    // ✅ COMPUTER TIMEOUT: Log parameters for debugging
    console.log('⏸️ COMPUTER TIMEOUT: Building navigation params', {
      computerTimeout: computerTimeout,
      computerTeamName: computerTeamName,
      gameId: gameIdToUse,
      currentQuarter: currentQuarter
    });
    
    // ✅ SS&S: Use unified helper to build params (gameIdToUse includes URL fallback for Single Game)
    const params = helper.buildGameNavigationParams({
        sourceParams: urlParams,
        targetQuarter: currentQuarter,
        gameId: gameIdToUse,
        resumeFromTimeout: true, // ✅ TIMEOUT: Always resuming from timeout (any quarter)
        lineup: lineup,
        myTeamSide: myTeamSide || myTeamSideFallback || 'home',
        clock: clock, // ✅ TIMEOUT: Pass clock to preserve time remaining
        computerTimeout: computerTimeout, // ✅ COMPUTER TIMEOUT: Pass flag for computer timeout
        computerTeamName: computerTeamName, // ✅ COMPUTER TIMEOUT: Pass computer team name
        overrides: {
            home: homeTeam || homeTeamFallback || '',
            away: awayTeam || awayTeamFallback || '',
            home_id: homeId,
            away_id: awayId,
            my_team: myTeamSide || myTeamSideFallback || 'home',
            team_id: teamId || userTeamIdParam, // ✅ SS&S: Prefer team_id, fallback to user_team_id
            user_team_id: userTeamIdParam, // Keep for backward compatibility
            franchise_id: franchiseId,
            week: weekParam,
            tournament_id: tournamentId,
            mode: modeParam,
            home_score: homeScore ?? undefined,
            away_score: awayScore ?? undefined
        }
    });
    
    // ✅ COMPUTER TIMEOUT: Log final params to verify computer timeout params are included
    console.log('⏸️ COMPUTER TIMEOUT: Final navigation params', {
      hasComputerTimeout: params.has('computer_timeout'),
      computerTimeoutValue: params.get('computer_timeout'),
      computerTeamNameValue: params.get('computer_team_name'),
      fullUrl: `/set-lineup.html?${params.toString()}`
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
        
        // ✅ SS&S: Removed URL param approach - database is single source of truth
        // Game plan settings will be loaded from database when Game Plan page loads
    } catch (error) {
        console.error('❌ TIMEOUT: Error fetching lineup/game plan:', error);
        // Continue navigation even if fetch fails
    }
    
    // Navigate to lineup screen
    window.location.href = `/set-lineup.html?${params.toString()}`;
}

// Progress bar functions removed - no longer needed

