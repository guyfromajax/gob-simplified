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
let timeoutQueuedAtTurnIndex = null; // Track which turn index the timeout was queued at
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
    
    // Load sound effects
    try {
        // Use API_CONFIG to get correct static path for local vs production
        const API_CONFIG = window.API_CONFIG;
        const staticPath = API_CONFIG ? API_CONFIG.getStaticPath() : '/static';
        
        // Button click sound (plays when button is clicked)
        const clickSoundPath = `${staticPath}/sounds/buttonClickSound.wav`;
        timeoutSound = new Audio(clickSoundPath);
        timeoutSound.volume = 0.5; // Set volume to 50%
        console.log('✅ [TIMEOUT] Click sound loaded:', clickSoundPath);
        
        // Airhorn sound (plays when timeout executes/popup appears)
        const airhornPath = `${staticPath}/sounds/Timeout - Airhorn.mp3`;
        airhornSound = new Audio(airhornPath);
        airhornSound.volume = 0.7; // Set volume to 70%
        console.log('✅ [TIMEOUT] Airhorn sound loaded:', airhornPath);
    } catch (error) {
        console.warn('⚠️ [TIMEOUT] Could not load sound effects:', error);
    }
    
    button.addEventListener('click', handleTimeoutButtonClick);
    buttonInitialized = true;
    
    // Make button always live (enabled)
    updateTimeoutButtonState(true, 'Timeout available');
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
 * Update button state (always live now, but manages highlight)
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
    
    // Button is always enabled now
    button.disabled = false;
    button.style.opacity = '1';
    button.style.cursor = 'pointer';
    button.title = timeoutQueued ? 'Cancel Timeout' : 'Call Timeout';
}

/**
 * Check if user team is on offense for current turn
 */
function isUserTeamOnOffense(scene, turnData) {
    if (!scene || !turnData) {
        return false;
    }
    
    // Get user team ID
    const userTeamSide = scene.userTeamSide || scene.simData?.user_team_side;
    if (!userTeamSide) {
        return false;
    }
    
    // Get possession team ID from turn data
    const possessionTeamId = turnData.possession_team_id || turnData.offense_team_id;
    if (!possessionTeamId) {
        return false;
    }
    
    // Get user team ID based on side
    const homeTeamId = scene.simData?.home_team_id;
    const awayTeamId = scene.simData?.away_team_id;
    const userTeamId = userTeamSide === 'home' ? homeTeamId : awayTeamId;
    
    // Compare possession team with user team
    return String(possessionTeamId) === String(userTeamId);
}

/**
 * Check if timeout is eligible for current turn
 * Eligible if:
 * 1. User team is on offense
 * 2. Turn is BASELINE_INBOUND
 * 3. Turn is SIDE_INBOUND
 */
export function checkTimeoutEligibility(scene, turnData) {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return false;
    }
    
    ensureButtonInitialized();
    
    if (!scene || !turnData) {
        return false;
    }
    
    const currentTurn = turnData?.current_turn || turnData?.result_type;
    
    // Check if it's a BIP or SIP turn
    if (currentTurn === 'SIDE_INBOUND' || currentTurn === 'BASELINE_INBOUND') {
        return true;
    }
    
    // Check if user team is on offense
    if (isUserTeamOnOffense(scene, turnData)) {
        return true;
    }
    
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
    timeoutQueuedAtTurnIndex = null;
    updateButtonHighlight(false);
    updateTimeoutButtonState(true, 'Timeout available');
}

/**
 * Check if we should kill the current turn instantly (during active turn)
 * Conditions:
 * 1. User team is on offense (any turn type) → kill instantly
 * 2. BIP or SIP turn (any team) → kill instantly, UNLESS we've transitioned to HCO/FCP/HCT and away team is on offense
 */
export function shouldKillCurrentTurnInstantly(scene, turnData) {
    if (!ENABLE_TIMEOUT_BUTTON || !timeoutQueued) {
        return false;
    }
    
    if (!scene || !turnData) {
        return false;
    }
    
    const currentTurn = turnData?.current_turn || turnData?.result_type;
    
    // Condition 1: User team is on offense (any turn type) → kill instantly
    if (isUserTeamOnOffense(scene, turnData)) {
        return true;
    }
    
    // Condition 2: BIP or SIP turn
    if (currentTurn === 'SIDE_INBOUND' || currentTurn === 'BASELINE_INBOUND') {
        // Kill instantly for BIP/SIP, but only if we haven't transitioned to next turn
        // Check if we're still in the inbound phase (not yet in HCO/FCP/HCT)
        const isInboundPhase = scene.stateMachine?.is('Inbound') || 
                               scene.isInboundSetup === true;
        
        if (isInboundPhase) {
            return true; // Still in BIP/SIP phase, kill instantly
        }
        
        // We've transitioned past BIP/SIP to HCO/FCP/HCT
        // Only kill if user team is on offense (already checked above, so return false)
        // If away team is on offense, don't kill
        return false;
    }
    
    return false;
}

/**
 * Kill current turn instantly (pause tweens, set flags, execute timeout)
 */
export async function killCurrentTurnAndExecuteTimeout(scene, turnData) {
    if (!ENABLE_TIMEOUT_BUTTON || !timeoutQueued) {
        return false;
    }
    
    console.log('⏸️ TIMEOUT: Killing current turn instantly');
    
    // Pause all tweens immediately
    if (scene.tweens) {
        scene.tweens.pauseAll();
        console.log('⏸️ TIMEOUT: Paused all tweens');
    }
    
    // Set flag to stop animation loop
    scene.timeoutCalled = true;
    
    // Execute the timeout
    await handleTimeoutButtonClick(true); // Pass true to skip toggle (just execute)
    return true;
}

/**
 * Check if timeout is queued and should be executed
 * Called at the start of each turn
 * Only executes if:
 * 1. Timeout is queued
 * 2. Current turn is eligible
 * 3. This is a different turn than when it was queued (wait for NEXT eligible turn)
 */
export async function checkAndExecuteQueuedTimeout(scene, turnData) {
    if (!ENABLE_TIMEOUT_BUTTON || !timeoutQueued) {
        return false;
    }
    
    // Get current turn index
    const currentTurnIndex = turnData?.index || scene.currentTurn || null;
    
    // Only execute if this is a different turn than when it was queued
    // This ensures we wait for the NEXT eligible turn, not execute on the same turn
    if (timeoutQueuedAtTurnIndex !== null && currentTurnIndex !== null) {
        if (currentTurnIndex === timeoutQueuedAtTurnIndex) {
            // Same turn as when queued, don't execute yet
            console.log('⏸️ TIMEOUT: Same turn as when queued, waiting for next turn');
            return false;
        }
    }
    
    // Check if current turn is eligible
    if (checkTimeoutEligibility(scene, turnData)) {
        // Execute the timeout
        console.log('⏸️ TIMEOUT: Executing at start of eligible turn', currentTurnIndex);
        await handleTimeoutButtonClick(true); // Pass true to skip toggle (just execute)
        return true;
    }
    
    return false;
}

/**
 * Handle timeout button click
 * @param {boolean} executeOnly - If true, execute timeout without toggling state (used when eligible turn is reached)
 */
async function handleTimeoutButtonClick(executeOnly = false) {
    if (!ENABLE_TIMEOUT_BUTTON) {
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button) {
        return;
    }
    
    // Get game context from scene
    const scene = window.currentGameScene;
    
    if (!scene) {
        console.error('❌ TIMEOUT: Cannot access game scene');
        return;
    }
    
    // If executeOnly is false, toggle the queue state
    if (!executeOnly) {
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
        
        if (timeoutQueued) {
            // Store the current turn index when queued (to ensure we wait for NEXT eligible turn)
            const currentTurnIndex = scene.currentTurn || scene.currentTurnData?.index || null;
            timeoutQueuedAtTurnIndex = currentTurnIndex;
            updateButtonHighlight(true);
            updateTimeoutButtonState(true, 'Timeout queued');
            console.log('⏸️ TIMEOUT: Queued at turn index', currentTurnIndex);
        } else {
            timeoutQueuedAtTurnIndex = null;
            updateButtonHighlight(false);
            updateTimeoutButtonState(true, 'Timeout available');
            console.log('⏸️ TIMEOUT: Cancelled - removed from queue');
        }
        
        // If we're toggling off, don't execute
        if (!timeoutQueued) {
            return;
        }
        
        // Check if current turn is eligible
        const currentTurnData = scene.currentTurnData || {};
        if (checkTimeoutEligibility(scene, currentTurnData)) {
            // Current turn is eligible, execute immediately
            console.log('⏸️ TIMEOUT: Current turn is eligible, executing immediately');
            // Continue to execute timeout below (don't return)
        } else {
            // Not eligible, queue and wait for next eligible turn
            console.log('⏸️ TIMEOUT: Queued - will execute at start of next eligible turn');
            return;
        }
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
        
        // Show popup first, then navigate when user clicks "Go To Timeout" button
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
    
    // Add click handler for button
    const goToTimeoutBtn = popup.querySelector('.go-to-timeout-button');
    goToTimeoutBtn.addEventListener('click', async () => {
        popup.remove();
        // Navigate to lineup screen
        await showTimeoutPopup(timeoutResult, gameId, scene);
    });
    
    document.body.appendChild(popup);
}

/**
 * Show timeout popup and navigate to lineup screen
 * @param {Object} timeoutResult - Timeout result object
 * @param {string} gameId - Game ID
 * @param {Object} scene - Game scene object
 * @param {boolean} [computerTimeout=false] - Whether this is a computer timeout
 * @param {string} [computerTeamName] - Name of the computer team that called timeout
 */
export async function showTimeoutPopup(timeoutResult, gameId, scene, computerTimeout = false, computerTeamName = null) {
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
    
    // ✅ TIMEOUT: Get clock from API response first (backend source of truth - most reliable)
    // The /api/call-timeout endpoint returns the current clock at the moment the timeout is called
    let clock = null;
    if (timeoutResult && timeoutResult.clock) {
        clock = timeoutResult.clock;
        console.log(`✅ TIMEOUT: Using clock from API response: ${clock}`);
    }
    
    // Fallback to DOM element (what's actually displayed to user)
    if (!clock) {
        const clockEl = document.getElementById('game-clock');
        if (clockEl && clockEl.textContent && clockEl.textContent.trim()) {
            clock = clockEl.textContent.trim();
            console.log(`✅ TIMEOUT: Using clock from DOM element: ${clock}`);
        }
    }
    
    // Fallback to scene.simData.clock (updated by updateScoreboard as turns are processed)
    if (!clock) {
        clock = scene.simData?.clock || null;
        if (clock) {
            console.log(`✅ TIMEOUT: Using clock from scene.simData: ${clock}`);
        }
    }
    
    // Fallback to last processed turn (if turns array exists)
    if (!clock && scene.simData?.turns && Array.isArray(scene.simData.turns) && scene.simData.turns.length > 0) {
        const lastTurn = scene.simData.turns[scene.simData.turns.length - 1];
        clock = lastTurn?.clock || lastTurn?.game_clock || null;
        if (clock) {
            console.log(`✅ TIMEOUT: Using clock from last processed turn: ${clock}`);
        }
    }
    
    // Fallback to URL params (for initial load scenarios)
    if (!clock) {
        clock = urlParams.get('clock');
        if (clock) {
            console.log(`✅ TIMEOUT: Using clock from URL params: ${clock}`);
        }
    }
    
    // Final fallback: default to 8:00 if no clock found
    if (!clock) {
        clock = '8:00';
        console.warn(`⚠️ TIMEOUT: No clock found, defaulting to ${clock}`);
    }
    
    // Build lineup object from scene
    const homeLineup = scene.homeLineup || {};
    const awayLineup = scene.awayLineup || {};
    const lineup = myTeamSide === 'home' ? homeLineup : awayLineup;
    
    // ✅ COMPUTER TIMEOUT: Log parameters for debugging
    console.log('⏸️ COMPUTER TIMEOUT: Building navigation params', {
      computerTimeout: computerTimeout,
      computerTeamName: computerTeamName,
      gameId: gameId,
      currentQuarter: currentQuarter
    });
    
    // ✅ SS&S: Use unified helper to build params
    const params = helper.buildGameNavigationParams({
        sourceParams: urlParams,
        targetQuarter: currentQuarter,
        gameId: gameId,
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
            mode: modeParam
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

