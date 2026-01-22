/**
 * Pointer Validation Utility
 * Phase 2: Validate that pointers (game_id, franchise_id, tournament_id) point to existing documents
 * 
 * This utility provides functions to validate pointers before making API calls or navigating,
 * ensuring we fail loudly when pointers are invalid.
 */

/**
 * Validate a pointer by checking if it points to an existing document
 * 
 * @param {string} pointerType - Type of pointer ('game_id', 'franchise_id', 'tournament_id')
 * @param {string} pointerValue - Value of the pointer to validate
 * @returns {Promise<boolean>} - True if valid, throws error if invalid
 */
async function validatePointer(pointerType, pointerValue) {
  if (!pointerValue) {
    throw new Error(`${pointerType} is required but missing`);
  }

  try {
    const API_CONFIG = window.API_CONFIG;
    if (!API_CONFIG) {
      console.error('❌ [VALIDATE-POINTER] API_CONFIG not available');
      throw new Error('API configuration not available');
    }

    const params = new URLSearchParams({
      pointer_type: pointerType,
      pointer_value: pointerValue
    });

    const response = await fetch(`${API_CONFIG.buildUrl('/api/validate-pointer')}?${params.toString()}`);
    
    if (response.ok) {
      const data = await response.json();
      console.log(`✅ [VALIDATE-POINTER] ${pointerType} is valid:`, data);
      return true;
    } else {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      const errorMsg = errorData.detail || `Failed to validate ${pointerType}`;
      console.error(`❌ [VALIDATE-POINTER] ${pointerType} validation failed:`, errorMsg);
      
      // ✅ Phase 4: Show missing truth error screen for 404 (document not found)
      if (response.status === 404 && window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
        const mode = new URLSearchParams(window.location.search).get('mode') || 'single';
        window.ErrorHandler.showMissingTruthError({
          pointerType,
          pointerValue,
          message: errorMsg,
          mode,
          recoveryOptions: {
            redirectTo: mode === 'single' ? 'mode-select' : (mode === 'franchise' ? 'franchise-select' : 'tournament-select'),
            redirectLabel: mode === 'single' ? 'Go to Mode Select' : (mode === 'franchise' ? 'Go to Franchise Select' : 'Go to Tournament Select')
          }
        });
      }
      
      throw new Error(errorMsg);
    }
  } catch (error) {
    console.error(`❌ [VALIDATE-POINTER] Error validating ${pointerType}:`, error);
    throw error;
  }
}

/**
 * Validate game_id
 */
async function validateGameId(gameId) {
  return validatePointer('game_id', gameId);
}

/**
 * Validate franchise_id
 */
async function validateFranchiseId(franchiseId) {
  return validatePointer('franchise_id', franchiseId);
}

/**
 * Validate tournament_id
 */
async function validateTournamentId(tournamentId) {
  return validatePointer('tournament_id', tournamentId);
}

/**
 * Validate all pointers in URL params based on mode
 * 
 * @param {URLSearchParams} urlParams - URL parameters
 * @param {string} mode - Game mode ('single', 'franchise', 'tournament')
 * @returns {Promise<boolean>} - True if all required pointers are valid
 */
async function validatePointersForMode(urlParams, mode) {
  const validations = [];

  if (mode === 'single') {
    const gameId = urlParams.get('game_id');
    if (gameId) {
      validations.push(validateGameId(gameId));
    }
  } else if (mode === 'franchise') {
    const franchiseId = urlParams.get('franchise_id');
    if (franchiseId) {
      validations.push(validateFranchiseId(franchiseId));
    }
  } else if (mode === 'tournament') {
    const tournamentId = urlParams.get('tournament_id');
    if (tournamentId) {
      validations.push(validateTournamentId(tournamentId));
    }
  }

  if (validations.length === 0) {
    // No pointers to validate (e.g., new game)
    return true;
  }

  try {
    await Promise.all(validations);
    return true;
  } catch (error) {
    console.error('❌ [VALIDATE-POINTERS] Pointer validation failed:', error);
    throw error;
  }
}

// Expose globally
if (typeof window !== 'undefined') {
  window.PointerValidation = {
    validatePointer,
    validateGameId,
    validateFranchiseId,
    validateTournamentId,
    validatePointersForMode
  };
}

