/**
 * Defense Matchups Popup
 * 
 * Displays a popup overlay on court.html that lets the user set custom
 * man-to-man defensive matchups via drag-and-drop.
 * 
 * Shows after:
 * - Start of Q1
 * - Quarter breaks
 * - Timeouts
 * - Player foul outs
 */

// Position colors for user team
const POSITION_COLORS = {
    "PG": "#ff69b4",  // Pink
    "SG": "#ff8c00",  // Orange
    "SF": "#ffd700",  // Yellow
    "PF": "#87ceeb",  // Light blue
    "C": "#9370db"   // Purple
};

// Position order
const POSITIONS = ["PG", "SG", "SF", "PF", "C"];

let dontShowAgainThisGame = false; // Track "Don't show again" checkbox state

/**
 * Show the defense matchups popup
 * @param {string} gameId - Game ID
 * @param {Object} scene - Game scene object
 * @returns {Promise} - Resolves when user submits matchups (or closes popup)
 */
export async function showDefenseMatchupsPopup(gameId, scene) {
    // Check if user has checked "Don't show again this game"
    if (dontShowAgainThisGame) {
        return Promise.resolve();
    }
    
    // Remove any existing popup
    const existingPopup = document.querySelector('.defense-matchups-popup');
    if (existingPopup) {
        existingPopup.remove();
    }
    
    return new Promise((resolve) => {
        try {
            // Fetch lineup data
            const API_CONFIG = window.API_CONFIG;
            if (!API_CONFIG) {
                console.error("❌ DEFENSE MATCHUPS: API_CONFIG not available");
                resolve();
                return;
            }
            
            fetch(API_CONFIG.buildUrl(`/api/game/${gameId}/lineup-for-matchups`))
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Failed to fetch lineup data: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const { user_team, computer_team, current_matchups } = data;
                    
                    // Create popup
                    const popup = createPopupElement(user_team, computer_team, current_matchups, gameId);
                    document.body.appendChild(popup);
                    
                    // Initialize drag-and-drop (pass resolve so submit resolves the promise)
                    initializeDragAndDrop(popup, gameId, resolve);
                })
                .catch(error => {
                    console.error("❌ DEFENSE MATCHUPS: Failed to show popup:", error);
                    // Don't block gameplay if popup fails - resolve immediately
                    resolve();
                });
        } catch (error) {
            console.error("❌ DEFENSE MATCHUPS: Failed to show popup:", error);
            resolve();
        }
    });
}

/**
 * Create the popup DOM element
 */
function createPopupElement(userTeam, computerTeam, currentMatchups, gameId) {
    const popup = document.createElement('div');
    popup.className = 'defense-matchups-popup';
    
    // Store initial user team order (default: PG, SG, SF, PF, C)
    const initialOrder = POSITIONS.slice(); // Copy array
    popup.dataset.userTeamOrder = JSON.stringify(initialOrder);
    
    // Store user team and computer team data for re-rendering
    popup.dataset.userTeamData = JSON.stringify(userTeam);
    popup.dataset.computerTeamData = JSON.stringify(computerTeam);
    
    // Build user team rows (in initial order)
    const userRows = initialOrder.map(pos => {
        const player = userTeam.players.find(p => p.position === pos);
        if (!player) return '';
        return createPlayerRow(player, 'user', pos, currentMatchups);
    }).join('');
    
    // Build computer team rows
    const computerRows = POSITIONS.map(pos => {
        const player = computerTeam.players.find(p => p.position === pos);
        if (!player) return '';
        const guardingUserPos = player.guarding_user_position || pos;
        return createPlayerRow(player, 'computer', pos, currentMatchups, guardingUserPos);
    }).join('');
    
    // Store initial matchups in popup data attribute
    popup.dataset.matchups = JSON.stringify(currentMatchups);
    
    // Get team colors with fallbacks
    const userPrimaryColor = userTeam.primary_color || "#000000";
    const userSecondaryColor = userTeam.secondary_color || "#ffffff";
    const computerPrimaryColor = computerTeam.primary_color || "#000000";
    const computerSecondaryColor = computerTeam.secondary_color || "#ffffff";
    
    popup.innerHTML = `
        <div class="defense-matchups-content">
            <h2>DEFENSE MATCHUPS</h2>
            <div class="matchups-container">
                <div class="team-column user-team-column">
                    <div class="team-header" style="background-color: ${userPrimaryColor}; color: ${userSecondaryColor}; border: 2px solid ${userSecondaryColor};">${userTeam.team_name}</div>
                    <div class="player-rows">
                        ${userRows}
                    </div>
                </div>
                <div class="team-column computer-team-column">
                    <div class="team-header" style="background-color: ${computerPrimaryColor}; color: ${computerSecondaryColor}; border: 2px solid ${computerSecondaryColor};">${computerTeam.team_name}</div>
                    <div class="player-rows">
                        ${computerRows}
                    </div>
                </div>
            </div>
            <div class="matchups-controls">
                <button class="submit-matchups-button">Submit Defense Matchups</button>
                <label class="dont-show-again-checkbox">
                    <input type="checkbox" id="dont-show-again-checkbox">
                    <span>Don't show this pop up again this game</span>
                </label>
            </div>
        </div>
    `;
    
    // Add styles if not already present
    if (!document.getElementById('defense-matchups-popup-styles')) {
        addPopupStyles();
    }
    
    return popup;
}

/**
 * Format player name as "First Initial. Last Name"
 * @param {string} fullName - Full player name (e.g., "Kermit Prospect")
 * @returns {string} - Formatted name (e.g., "K. Prospect")
 */
function formatPlayerName(fullName) {
    if (!fullName) return '';
    const parts = fullName.trim().split(' ');
    if (parts.length === 1) return parts[0];
    const firstName = parts[0];
    const lastName = parts.slice(1).join(' ');
    return `${firstName.charAt(0).toUpperCase()}. ${lastName}`;
}

/**
 * Create a player row element
 */
function createPlayerRow(player, teamType, position, currentMatchups, guardingUserPos = null) {
    const isUserTeam = teamType === 'user';
    const borderColor = isUserTeam 
        ? POSITION_COLORS[position] 
        : (guardingUserPos ? POSITION_COLORS[guardingUserPos] : '#c0c0c0');
    
    // Position square color
    const positionSquareColor = isUserTeam
        ? POSITION_COLORS[position]
        : (guardingUserPos ? POSITION_COLORS[guardingUserPos] : '#c0c0c0');
    
    // Build stat strip - single integer values (divide by 10, floor) like lineup screen
    let statStrip = '';
    if (isUserTeam) {
        // User team: ID, OD, AG, ST, ND, IQ, NG, DEF%
        const attrs = player.attributes;
        statStrip = `
            <div class="stat-strip">
                <div class="stat-item"><span class="stat-label">ID</span><span class="stat-value">${Math.floor((attrs.ID || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">OD</span><span class="stat-value">${Math.floor((attrs.OD || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">AG</span><span class="stat-value">${Math.floor((attrs.AG || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">ST</span><span class="stat-value">${Math.floor((attrs.ST || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">ND</span><span class="stat-value">${Math.floor((attrs.ND || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">IQ</span><span class="stat-value">${Math.floor((attrs.IQ || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">NG</span><span class="stat-value">${attrs.NG || 0}%</span></div>
                <div class="stat-item"><span class="stat-label">DEF%</span><span class="stat-value">${attrs['DEF%'] || 0}%</span></div>
            </div>
        `;
    } else {
        // Computer team: SC, SH, AG, ST, ND, IQ, NG, PTS
        const stats = player.stats;
        statStrip = `
            <div class="stat-strip">
                <div class="stat-item"><span class="stat-label">SC</span><span class="stat-value">${Math.floor((stats.SC || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">SH</span><span class="stat-value">${Math.floor((stats.SH || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">AG</span><span class="stat-value">${Math.floor((stats.AG || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">ST</span><span class="stat-value">${Math.floor((stats.ST || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">ND</span><span class="stat-value">${Math.floor((stats.ND || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">IQ</span><span class="stat-value">${Math.floor((stats.IQ || 0) / 10)}</span></div>
                <div class="stat-item"><span class="stat-label">NG</span><span class="stat-value">${stats.NG || 0}%</span></div>
                <div class="stat-item"><span class="stat-label">PTS</span><span class="stat-value">${stats.PTS || 0}</span></div>
            </div>
        `;
    }
    
    return `
        <div class="player-row ${teamType}-team-row" 
             data-position="${position}" 
             data-team-type="${teamType}"
             data-player-id="${player.player_id}"
             style="border: 2px solid ${borderColor};">
            <div class="position-square" style="background-color: ${positionSquareColor};">
                ${position}
            </div>
            <img class="player-headshot" src="${player.headshot_url}" alt="${player.name}" onerror="this.style.display='none';">
            <div class="player-name">${formatPlayerName(player.name)}</div>
            ${statStrip}
        </div>
    `;
}

/**
 * Initialize drag-and-drop functionality
 * Uses data + re-render pattern (like Lineup Screen) for robust drag-and-drop
 * User can only drag and drop within the user team column to swap positions
 * @param {HTMLElement} popup - Popup element
 * @param {string} gameId - Game ID
 * @param {Function} onResolve - Callback to resolve promise when popup is closed
 */
function initializeDragAndDrop(popup, gameId, onResolve) {
    const userRowsContainer = popup.querySelector('.user-team-column .player-rows');
    if (!userRowsContainer) {
        return;
    }
    
    // Get initial order from popup data (array of positions in current order)
    let userTeamOrder = getCurrentUserTeamOrder(popup);
    
    // Make all user rows draggable
    const userRows = popup.querySelectorAll('.user-team-row');
    userRows.forEach(row => {
        row.draggable = true;
    });
    
    // Event delegation on container (like Lineup Screen pattern)
    // dragstart - store dragged row's position in dataTransfer
    userRowsContainer.addEventListener('dragstart', (e) => {
        const row = e.target.closest('.user-team-row');
        if (!row) return;
        
        const position = row.dataset.position;
        if (position) {
            e.dataTransfer.setData('text/plain', position);
            e.dataTransfer.setData('application/x-user-position', position);
            e.dataTransfer.effectAllowed = 'move';
            row.style.opacity = '0.5';
        } else {
            e.preventDefault();
        }
    });
    
    // dragend - reset visual state
    userRowsContainer.addEventListener('dragend', (e) => {
        const row = e.target.closest('.user-team-row');
        if (row) {
            row.style.opacity = '1';
        }
        // Reset all row backgrounds
        const allRows = popup.querySelectorAll('.user-team-row');
        allRows.forEach(r => r.style.backgroundColor = '');
    });
    
    // dragover - allow drop and show visual feedback
    userRowsContainer.addEventListener('dragover', (e) => {
        const row = e.target.closest('.user-team-row');
        if (row) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            row.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
        }
    });
    
    // dragleave - remove highlight
    userRowsContainer.addEventListener('dragleave', (e) => {
        const row = e.target.closest('.user-team-row');
        if (row) {
            row.style.backgroundColor = '';
        }
    });
    
    // drop - handle the swap (data + re-render pattern)
    userRowsContainer.addEventListener('drop', (e) => {
        const targetRow = e.target.closest('.user-team-row');
        if (!targetRow) return;
        
        e.preventDefault();
        targetRow.style.backgroundColor = '';
        
        // Get dragged position from dataTransfer
        const draggedPosition = e.dataTransfer.getData('application/x-user-position');
        if (!draggedPosition) return;
        
        const targetPosition = targetRow.dataset.position;
        if (draggedPosition === targetPosition) return; // Same row, no swap
        
        // Update data structure (swap positions in order array)
        const draggedIndex = userTeamOrder.indexOf(draggedPosition);
        const targetIndex = userTeamOrder.indexOf(targetPosition);
        
        if (draggedIndex === -1 || targetIndex === -1) return; // Invalid positions
        
        // Swap in data structure
        userTeamOrder[draggedIndex] = targetPosition;
        userTeamOrder[targetIndex] = draggedPosition;
        
        // Store updated order in popup
        popup.dataset.userTeamOrder = JSON.stringify(userTeamOrder);
        
        // Re-render user team rows based on new order
        renderUserTeamRows(popup, userTeamOrder);
        
        // Recalculate matchups based on new order
        const newMatchups = calculateMatchupsFromOrder(userTeamOrder);
        storeMatchupsInPopup(popup, newMatchups);
        
        // Update visual display (computer team colors)
        updatePopupDisplay(popup, newMatchups);
    });
    
    // Submit button handler
    const submitButton = popup.querySelector('.submit-matchups-button');
    submitButton.addEventListener('click', async () => {
        await handleSubmit(popup, gameId);
        if (onResolve) {
            onResolve(); // Resolve promise to allow animation to continue
        }
    });
    
    // Checkbox handler
    const checkbox = popup.querySelector('#dont-show-again-checkbox');
    checkbox.addEventListener('change', (e) => {
        dontShowAgainThisGame = e.target.checked;
    });
}

/**
 * Get current user team order from popup data
 */
function getCurrentUserTeamOrder(popup) {
    if (popup.dataset.userTeamOrder) {
        return JSON.parse(popup.dataset.userTeamOrder);
    }
    // Default order
    return POSITIONS.slice();
}

/**
 * Calculate matchups from user team order
 * Matchups: user position in slot X guards computer position X
 */
function calculateMatchupsFromOrder(userTeamOrder) {
    const matchups = {};
    userTeamOrder.forEach((userPosition, index) => {
        const slotPosition = POSITIONS[index]; // The slot they're in (PG slot, SG slot, etc.)
        matchups[userPosition] = slotPosition; // This user position guards the computer position in this slot
    });
    return matchups;
}

/**
 * Re-render user team rows based on current order (data + re-render pattern)
 */
function renderUserTeamRows(popup, userTeamOrder) {
    const userRowsContainer = popup.querySelector('.user-team-column .player-rows');
    if (!userRowsContainer) return;
    
    // Get user team data
    const userTeam = JSON.parse(popup.dataset.userTeamData);
    const currentMatchups = getCurrentMatchupsFromPopup(popup);
    
    // Build rows in new order
    const userRows = userTeamOrder.map(pos => {
        const player = userTeam.players.find(p => p.position === pos);
        if (!player) return '';
        return createPlayerRow(player, 'user', pos, currentMatchups);
    }).join('');
    
    // Replace container content
    userRowsContainer.innerHTML = userRows;
    
    // Re-attach draggable attribute to new rows
    const newRows = userRowsContainer.querySelectorAll('.user-team-row');
    newRows.forEach(row => {
        row.draggable = true;
    });
}

/**
 * Get current matchups from popup DOM
 * Uses a data attribute to track matchups more reliably
 */
function getCurrentMatchupsFromPopup(popup) {
    // Store matchups in popup data attribute for reliable tracking
    if (!popup.dataset.matchups) {
        // Initialize with defaults
        const defaults = {};
        POSITIONS.forEach(pos => {
            defaults[pos] = pos;
        });
        popup.dataset.matchups = JSON.stringify(defaults);
    }
    
    return JSON.parse(popup.dataset.matchups);
}

/**
 * Store matchups in popup data attribute
 */
function storeMatchupsInPopup(popup, matchups) {
    popup.dataset.matchups = JSON.stringify(matchups);
}

/**
 * Update popup display to reflect current matchups
 */
function updatePopupDisplay(popup, matchups) {
    const userRows = popup.querySelectorAll('.user-team-row');
    const computerRows = popup.querySelectorAll('.computer-team-row');
    
    // Update user team row borders (always match position color)
    userRows.forEach(row => {
        const userPos = row.dataset.position;
        const color = POSITION_COLORS[userPos];
        row.style.borderColor = color;
        
        // Update position square
        const positionSquare = row.querySelector('.position-square');
        positionSquare.style.backgroundColor = color;
    });
    
    // Update computer team row borders and position squares
    computerRows.forEach(row => {
        const compPos = row.dataset.position;
        // Find which user position guards this computer position
        let guardingUserPos = null;
        for (const [userPos, guardedPos] of Object.entries(matchups)) {
            if (guardedPos === compPos) {
                guardingUserPos = userPos;
                break;
            }
        }
        
        const color = guardingUserPos ? POSITION_COLORS[guardingUserPos] : '#c0c0c0';
        row.style.borderColor = color;
        
        // Update position square
        const positionSquare = row.querySelector('.position-square');
        positionSquare.style.backgroundColor = color;
    });
}

/**
 * Handle submit button click
 * @returns {Promise} - Resolves when submit is complete
 */
async function handleSubmit(popup, gameId) {
    const matchups = getCurrentMatchupsFromPopup(popup);
    
    try {
        const API_CONFIG = window.API_CONFIG;
        if (!API_CONFIG) {
            throw new Error("API_CONFIG not available");
        }
        
        const response = await fetch(API_CONFIG.buildUrl('/api/save-man-defense-matchups'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                game_id: gameId,
                matchups: matchups
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save matchups');
        }
        
        // Close popup
        popup.remove();
        
    } catch (error) {
        console.error("❌ DEFENSE MATCHUPS: Failed to save:", error);
        alert(`Failed to save matchups: ${error.message}`);
    }
}

/**
 * Add popup styles
 */
function addPopupStyles() {
    const style = document.createElement('style');
    style.id = 'defense-matchups-popup-styles';
    style.textContent = `
        .defense-matchups-popup {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10002;
        }

        .defense-matchups-content {
            background: #fff;
            border: 4px solid #c0c0c0;
            border-radius: 8px;
            padding: 20px 48px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            align-items: center;
            min-width: 1000px;
            max-width: 1200px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
        }

        .defense-matchups-content h2 {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a1a;
            margin: 0;
            font-family: 'Bebas Neue', sans-serif;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }

        .matchups-container {
            display: flex;
            gap: 32px;
            width: 100%;
        }

        .team-column {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .team-header {
            font-size: 18px;
            font-weight: 600;
            text-align: center;
            padding: 4px 12px;
            border-radius: 4px;
            font-family: 'Inter', sans-serif;
            letter-spacing: 0.5px;
            border: 2px solid;
        }

        .player-rows {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .player-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            border-radius: 4px;
            background: #fafafa;
            cursor: move;
            transition: background-color 0.15s ease;
        }

        .player-row:hover {
            background: #f0f0f0;
        }

        .user-team-row {
            cursor: grab;
        }

        .user-team-row:active {
            cursor: grabbing;
        }

        .computer-team-row {
            cursor: default;
        }

        .position-square {
            width: 42px;
            height: 42px;
            border: 2px solid #c0c0c0;
            border-radius: 3px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 20px;
            color: #fff;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
            flex-shrink: 0;
        }

        .player-headshot {
            width: 50px;
            height: 50px;
            border-radius: 3px;
            object-fit: cover;
            border: 2px solid #ddd;
            flex-shrink: 0;
        }

        .player-name {
            font-size: 14px;
            font-weight: 600;
            color: #1a1a1a;
            min-width: 90px;
            flex-shrink: 0;
            font-family: 'Inter', sans-serif;
        }

        .stat-strip {
            display: flex;
            gap: 6px;
            flex-wrap: nowrap;
            flex: 1;
            align-items: center;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1px;
            min-width: 28px;
        }

        .stat-label {
            font-size: 11px;
            color: #555;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            font-family: 'Inter', sans-serif;
        }

        .stat-value {
            font-size: 15px;
            color: #1a1a1a;
            font-weight: 700;
            font-family: 'Inter', sans-serif;
        }

        .matchups-controls {
            display: flex;
            flex-direction: column;
            gap: 8px;
            align-items: center;
            width: 100%;
            margin-top: 2px;
        }

        .submit-matchups-button {
            padding: 12px 32px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            background: #ff9800;
            color: #fff;
            transition: background-color 0.2s ease;
            font-family: 'Inter', sans-serif;
            letter-spacing: 0.3px;
        }

        .submit-matchups-button:hover {
            background: #f57c00;
        }

        .dont-show-again-checkbox {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            color: #555;
            cursor: pointer;
            font-family: 'Inter', sans-serif;
        }

        .dont-show-again-checkbox input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Reset the "Don't show again" flag (called at game start)
 */
export function resetDontShowAgainFlag() {
    dontShowAgainThisGame = false;
}

