function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

/**
 * Pointer Validation Utility
 * Phase 2: Validate that pointers (game_id, franchise_id) point to existing documents
 * 
 * This utility provides functions to validate pointers before making API calls or navigating,
 * ensuring we fail loudly when pointers are invalid.
 */

/**
 * Validate a pointer by checking if it points to an existing document
 * 
 * @param {string} pointerType - Type of pointer ('game_id', 'franchise_id')
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

    const params = emptyParams();
    params.set('pointer_type', pointerType);
    params.set('pointer_value', pointerValue);

    const response = await fetch(`${API_CONFIG.buildUrl('/api/validate-pointer')}?${params.toString()}`);
    
    if (response.ok) {
      const data = await response.json();
      return true;
    } else {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      const errorMsg = errorData.detail || `Failed to validate ${pointerType}`;
      console.error(`❌ [VALIDATE-POINTER] ${pointerType} validation failed:`, errorMsg);
      
      // ✅ Phase 4: Show missing truth error screen for 404 (document not found)
      if (response.status === 404 && window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
        const mode = liveParams().get('mode') || 'single';
        window.ErrorHandler.showMissingTruthError({
          pointerType,
          pointerValue,
          message: errorMsg,
          mode,
          recoveryOptions: {
            redirectTo: mode === 'franchise' ? 'franchise-select' : 'mode-select',
            redirectLabel: mode === 'franchise' ? 'Go to Franchise Select' : 'Go to Mode Select'
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
 * Validate all pointers in URL params based on mode
 * 
 * @param {Object} urlParams - URL parameters
 * @param {string} mode - Game mode ('single', 'franchise')
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
    validatePointersForMode
  };
}

