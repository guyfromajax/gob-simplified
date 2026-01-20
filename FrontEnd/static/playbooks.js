/**
 * Playbooks Page - State Management and UI Logic
 * 
 * Features:
 * - Six percentage sections (must total 100% each)
 * - Priority slots 1-6 for offense (unique assignment)
 * - Motion dropdowns (Inside/Attack/Outside)
 * - Persistence (localStorage with API interface)
 * - Validation and error handling
 */

// ============================================================================
// PLAY DATA DEFINITIONS
// ============================================================================

// Play data will be loaded from API, but we keep defense plays hardcoded for now
const DEFENSE_PLAY_DATA = {
  'man-defense': [
    { id: 'man-1', name: 'Man Defense' },
    { id: 'man-2', name: 'Man Defense Variant 2' },
    { id: 'man-3', name: 'Man Defense Variant 3' },
  ],
  'zone-defense': [
    { id: 'zone-1', name: '2-3 Zone' },
    { id: 'zone-2', name: '3-2 Zone' },
    { id: 'zone-3', name: '1-3-1 Zone' },
    { id: 'zone-4', name: 'Zone Variant 4' },
    { id: 'zone-5', name: 'Zone Variant 5' },
  ],
};

// Placeholder for plays that don't exist yet
const TO_BE_ADDED_PLACEHOLDER = { id: 'to-be-added', name: 'To Be Added' };

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

class PlaybooksState {
  constructor(playData = {}) {
    // Section data: { [playId]: { percentage: number, slot: number | null, dropdown?: string } }
    this.sections = {
      motion: {},
      'set-play-inside': {},
      'set-play-attack': {},
      'set-play-outside': {},
      'man-defense': {},
      'zone-defense': {},
    };
    
    // Slot assignments: { [slotNumber]: { section: string, playId: string, dropdown?: string } }
    this.slotAssignments = {};
    
    // Motion dropdown defaults
    this.motionDropdowns = {}; // { [playId]: 'Inside' | 'Attack' | 'Outside' }
    
    // Store play data for rendering (not used in state, but kept for compatibility)
    this.playData = playData;
    
    this.initDefaults();
  }
  
  initDefaults() {
    // Initialize motion plays (4 slots max)
    const motionPlays = this.playData.motion || [];
    const motionSlots = 4;
    
    for (let i = 0; i < motionSlots; i++) {
      const play = i < motionPlays.length ? motionPlays[i] : TO_BE_ADDED_PLACEHOLDER;
      // Generate unique ID for each slot (including placeholders)
      const playId = play.id || `motion-${i + 1}`;
      // For "To Be Added" placeholders, use unique ID
      const finalPlayId = (play.name === 'To Be Added') ? `motion-tba-${i + 1}` : playId;
      
      this.sections.motion[finalPlayId] = {
        percentage: i === 0 ? 100 : 0,
        slot: null,
      };
      
      if (play.name !== 'To Be Added') {
        // Don't set default here - let it be "-" initially, user must explicitly select "Inside"
        // this.motionDropdowns[finalPlayId] = 'Inside';
      }
    }
    
    // Initialize set play sections (3 slots each)
    const setPlaySections = [
      { key: 'set-play-inside', plays: this.playData.set_play_inside || [] },
      { key: 'set-play-attack', plays: this.playData.set_play_attack || [] },
      { key: 'set-play-outside', plays: this.playData.set_play_outside || [] },
    ];
    
    setPlaySections.forEach(({ key, plays }) => {
      for (let i = 0; i < 3; i++) {
        const play = i < plays.length ? plays[i] : TO_BE_ADDED_PLACEHOLDER;
        const playId = play.id || `${key}-${i + 1}`;
        // For "To Be Added" placeholders, use unique ID
        const finalPlayId = (play.name === 'To Be Added') ? `${key}-tba-${i + 1}` : playId;
        
        this.sections[key][finalPlayId] = {
          percentage: i === 0 ? 100 : 0,
          slot: null,
        };
      }
    });
    
    // Initialize defense plays (hardcoded for now)
    Object.keys(DEFENSE_PLAY_DATA).forEach(sectionKey => {
      const plays = DEFENSE_PLAY_DATA[sectionKey];
      plays.forEach((play, index) => {
        this.sections[sectionKey][play.id] = {
          percentage: index === 0 ? 100 : 0,
          slot: null,
        };
      });
    });
  }
  
  // Calculate section total
  getSectionTotal(sectionKey) {
    return Object.values(this.sections[sectionKey] || {})
      .reduce((sum, play) => sum + (play.percentage || 0), 0);
  }
  
  // Check if all sections total 100%
  areAllSectionsValid() {
    return Object.keys(this.sections).every(sectionKey => 
      this.getSectionTotal(sectionKey) === 100
    );
  }
  
  // Get slot assignment key for motion plays
  getMotionSlotKey(playId, dropdown) {
    return `motion:${playId}:${dropdown}`;
  }
  
  // Assign slot to a play
  assignSlot(slotNumber, sectionKey, playId, dropdown = null) {
    // Unassign from previous play if slot was already assigned
    if (this.slotAssignments[slotNumber]) {
      const prev = this.slotAssignments[slotNumber];
      if (prev.section === 'motion') {
        // For motion, we need to check all dropdown variants
        const prevPlay = this.sections.motion[prev.playId];
        if (prevPlay) {
          prevPlay.slot = null;
        }
      } else {
        const prevPlay = this.sections[prev.section]?.[prev.playId];
        if (prevPlay) {
          prevPlay.slot = null;
        }
      }
    }
    
    // Assign to new play
    if (sectionKey === 'motion') {
      if (!dropdown) {
        dropdown = this.motionDropdowns[playId] || '-';
      }
      this.slotAssignments[slotNumber] = {
        section: sectionKey,
        playId,
        dropdown,
      };
      // Note: We don't store slot on the play data for motion since it's dropdown-specific
      // Instead, we check slotAssignments directly
    } else {
      this.slotAssignments[slotNumber] = {
        section: sectionKey,
        playId,
      };
      this.sections[sectionKey][playId].slot = slotNumber;
    }
  }
  
  // Get slot number for a motion play with specific dropdown
  getMotionSlot(playId, dropdown) {
    for (const [slotNum, assignment] of Object.entries(this.slotAssignments)) {
      if (assignment.section === 'motion' &&
          assignment.playId === playId &&
          assignment.dropdown === dropdown) {
        return parseInt(slotNum);
      }
    }
    return null;
  }
  
  // Get assigned play name for a slot
  getAssignedPlayName(slotNumber, playData = null) {
    const assignment = this.slotAssignments[slotNumber];
    if (!assignment) return null;
    
    // Try to find play in loaded play data
    let play = null;
    if (playData) {
      if (assignment.section === 'motion') {
        play = playData.motion?.find(p => p.id === assignment.playId);
      } else if (assignment.section === 'set-play-inside') {
        play = playData.set_play_inside?.find(p => p.id === assignment.playId);
      } else if (assignment.section === 'set-play-attack') {
        play = playData.set_play_attack?.find(p => p.id === assignment.playId);
      } else if (assignment.section === 'set-play-outside') {
        play = playData.set_play_outside?.find(p => p.id === assignment.playId);
      }
    }
    
    // Fallback to defense plays (hardcoded)
    if (!play && DEFENSE_PLAY_DATA[assignment.section]) {
      play = DEFENSE_PLAY_DATA[assignment.section].find(p => p.id === assignment.playId);
    }
    
    if (!play) return null;
    
    // For motion, include dropdown (focus)
    if (assignment.section === 'motion') {
      return `${play.name} (${assignment.dropdown})`;
    }
    
    // For set plays, determine focus from section
    if (assignment.section === 'set-play-inside') {
      return `${play.name} (Inside)`;
    }
    if (assignment.section === 'set-play-attack') {
      return `${play.name} (Attack)`;
    }
    if (assignment.section === 'set-play-outside') {
      return `${play.name} (Outside)`;
    }
    
    return play.name;
  }
  
  // Serialize for persistence
  serialize() {
    return {
      sections: this.sections,
      slotAssignments: this.slotAssignments,
      motionDropdowns: this.motionDropdowns,
    };
  }
  
  // Deserialize from persistence
  deserialize(data) {
    if (data.sections) this.sections = data.sections;
    if (data.slotAssignments) this.slotAssignments = data.slotAssignments;
    // Merge persisted motionDropdowns with current state (don't overwrite existing values)
    if (data.motionDropdowns) {
      // Merge: persisted values take precedence, but current state remains for new plays
      this.motionDropdowns = { ...this.motionDropdowns, ...data.motionDropdowns };
    }
    // Ensure all motion plays have a dropdown value (default to "-" if missing)
    // This handles new plays that weren't in persisted data
    const motionPlays = this.playData.motion || [];
    motionPlays.forEach((play, index) => {
      const playId = play.id || `motion-${index + 1}`;
      if (!this.motionDropdowns[playId]) {
        this.motionDropdowns[playId] = '-';
      }
    });
  }
}

// ============================================================================
// PERSISTENCE LAYER
// ============================================================================

// ✅ MIGRATION (Task 6.2): Removed PlaybooksPersistence class
// Settings are now loaded/saved from database only (single source of truth)
// localStorage is only used for UI preferences (position filters, even distribution button states)

// ============================================================================
// UI CONTROLLER
// ============================================================================

class PlaybooksUI {
  constructor() {
    this.state = null; // Will be initialized after loading plays
    // ✅ MIGRATION (Task 6.2): Removed persistence - settings loaded from database only
    this.debounceTimer = null;
    this.playData = null;
    this.selectedPositions = []; // Array to track selected positions (max 2, FIFO)
    this.positionFilters = null; // Position filter mappings from API (play_id → position arrays)
    this.evenDistributionEnabled = {
      motion: false,
      'set-play-inside': false,
      'set-play-attack': false,
      'set-play-outside': false,
      'man-defense': false,
      'zone-defense': false
    }; // Track which sections have Even Distribution enabled
    this.hasUnsavedChanges = false; // Track if user has made changes since last submit
  }
  
  async init() {
    // Load plays from API first
    await this.loadPlays();
    
    // Initialize state with loaded plays
    this.state = new PlaybooksState(this.playData);
    
    // ✅ FIX: Load position filter selections BEFORE loadState() so that
    // redistributePercentagesEvenly() (if even_distribution_all is true) can
    // correctly filter plays based on selected positions
    this.loadPositionFilterSelections();
    
    // Load saved state (if any)
    await this.loadState();
    
    // Re-render assigned plays to ensure slot assignments are displayed
    this.renderAssignedPlays();
    
    this.renderAll();
    this.attachEventListeners();
    
    // Update Even Distribution button states after rendering (restored from localStorage)
    Object.keys(this.evenDistributionEnabled).forEach(sectionKey => {
      this.updateEvenDistributionButton(sectionKey);
    });
    
    // Update "Even Distribution - All" button state
    this.updateEvenDistributionAllButton();
    
    this.updateSubmitButton();
  }
  
  async loadPlays() {
    try {
      // Get URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      // Check multiple possible team_id parameter names (matching loadAndApplySlotAssignments pattern)
      let teamId = urlParams.get('team_id') || 
                   urlParams.get('user_team_id') || 
                   urlParams.get('home_id') || 
                   urlParams.get('away_id');
      
      // ✅ PHASE 1.1: Remove localStorage fallback - game_id must come from URL params only
      let gameId = urlParams.get('game_id') || null;
      
      const tournamentId = urlParams.get('tournament_id');
      const franchiseId = urlParams.get('franchise_id');
      
      console.log('🔍 [PLAYBOOKS] Loading plays with params:', {
        mode,
        teamId,
        gameId,
        tournamentId,
        franchiseId,
        allParams: Object.fromEntries(urlParams.entries())
      });
      
      if (!teamId) {
        console.warn('⚠️ No team_id found in URL params, using empty plays');
        this.playData = {
          motion: [],
          set_play_inside: [],
          set_play_attack: [],
          set_play_outside: []
        };
        return;
      }
      
      // Build API URL
      const params = new URLSearchParams();
      params.set('mode', mode);
      params.set('team_id', teamId);
      if (mode === 'single' && gameId) {
        params.set('game_id', gameId);
      } else if (mode === 'tournament' && tournamentId) {
        params.set('tournament_id', tournamentId);
      } else if (mode === 'franchise' && franchiseId) {
        params.set('franchise_id', franchiseId);
      }
      
        const response = await fetch(`${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`);
      if (response.ok) {
        const data = await response.json();
        
        // Store position filters from API
        this.positionFilters = data.position_filters || {
          standard: [],
          PG: [],
          SG: [],
          SF: [],
          PF: [],
          C: []
        };
        
        console.log('🔍 [POSITION FILTERS] Loaded from API:', this.positionFilters);
        
        // Store saved playbook percentages for later use
        this.savedPlaybookPercentages = data.playbook_percentages || {};
        console.log('🔍 [PLAYBOOKS LOAD] Loaded saved percentages from API:', this.savedPlaybookPercentages);
        console.log('🔍 [PLAYBOOKS LOAD] motion keys:', Object.keys(this.savedPlaybookPercentages.motion || {}));
        console.log('🔍 [PLAYBOOKS LOAD] set_play_inside keys:', Object.keys(this.savedPlaybookPercentages.set_play_inside || {}));
        console.log('🔍 [PLAYBOOKS LOAD] set_play_attack keys:', Object.keys(this.savedPlaybookPercentages.set_play_attack || {}));
        console.log('🔍 [PLAYBOOKS LOAD] set_play_outside keys:', Object.keys(this.savedPlaybookPercentages.set_play_outside || {}));
        if (this.savedPlaybookPercentages.motion) {
          const sample = Object.entries(this.savedPlaybookPercentages.motion).slice(0, 3);
          console.log('🔍 [PLAYBOOKS LOAD] Sample motion percentages:', sample);
        }
        
        // Store even_distribution_all flag from API
        this.evenDistributionAllFlag = data.even_distribution_all || false;
        console.log('🔍 [PLAYBOOKS] Loaded even_distribution_all flag from API:', this.evenDistributionAllFlag);
        
        // Convert API response to play data format
        this.playData = {
          motion: (data.motion || []).map((play, index) => ({
            id: `motion-${index + 1}`,
            name: play.name,
            play_id: play.play_id,
            play_type: play.play_type,
            play_focus: play.play_focus
          })),
          set_play_inside: (data.set_play_inside || []).map((play, index) => ({
            id: `set-inside-${index + 1}`,
            name: play.name,
            play_id: play.play_id,
            play_type: play.play_type,
            play_focus: play.play_focus
          })),
          set_play_attack: (data.set_play_attack || []).map((play, index) => ({
            id: `set-attack-${index + 1}`,
            name: play.name,
            play_id: play.play_id,
            play_type: play.play_type,
            play_focus: play.play_focus
          })),
          set_play_outside: (data.set_play_outside || []).map((play, index) => ({
            id: `set-outside-${index + 1}`,
            name: play.name,
            play_id: play.play_id,
            play_type: play.play_type,
            play_focus: play.play_focus
          }))
        };
        
        console.log('✅ Loaded plays from API:', this.playData);
        console.log('🔍 [DEBUG OUTSIDE PLAYS] API response set_play_outside:', data.set_play_outside);
        console.log('🔍 [DEBUG OUTSIDE PLAYS] Mapped set_play_outside:', this.playData.set_play_outside);
        console.log('🔍 [DEBUG OUTSIDE PLAYS] Count:', this.playData.set_play_outside.length);
      } else {
        console.error('❌ Failed to load plays from API:', response.status);
        // Fallback to empty plays
        this.playData = {
          motion: [],
          set_play_inside: [],
          set_play_attack: [],
          set_play_outside: []
        };
      }
    } catch (error) {
      console.error('❌ Error loading plays:', error);
      // Fallback to empty plays
      this.playData = {
        motion: [],
        set_play_inside: [],
        set_play_attack: [],
        set_play_outside: []
      };
    }
  }
  
  async loadState() {
    // ✅ SS&S: Always load from database (single source of truth)
    // Load from API (slot assignments, motion dropdowns, and percentages)
    await this.loadSlotAssignmentsFromAPI();
    await this.loadPlaybookPercentagesFromAPI();
    
    // ✅ FIX: even_distribution_all flag controls UI state only, NOT automatic redistribution on load
    // Saved percentages are always respected regardless of flag value
    // The flag indicates "user last used even distribution" but percentages were already saved when distributed
    if (this.evenDistributionAllFlag === true) {
      console.log('🔍 [PLAYBOOKS] even_distribution_all is true - syncing UI state to reflect flag');
      // Sync button states to show that even distribution was last used
      const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
      offenseSections.forEach(sectionKey => {
        this.evenDistributionEnabled[sectionKey] = true;
        this.updateEvenDistributionButton(sectionKey);
      });
      // Update "Even Distribution - All" button state
      this.updateEvenDistributionAllButton();
      // ✅ Saved percentages are already loaded and displayed (they were saved when user clicked "Even Distribution - All")
    } else {
      // Flag is false - saved percentages are already loaded, just sync button states
      console.log('🔍 [PLAYBOOKS] even_distribution_all is false, using saved percentages');
      const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
      offenseSections.forEach(sectionKey => {
        this.evenDistributionEnabled[sectionKey] = false;
        this.updateEvenDistributionButton(sectionKey);
      });
      this.updateEvenDistributionAllButton();
    }
    
    // Update button visual states after loading
    Object.keys(this.evenDistributionEnabled).forEach(sectionKey => {
      this.updateEvenDistributionButton(sectionKey);
    });
  }
  
  async loadPlaybookPercentagesFromAPI() {
    // Apply saved percentages from API to state
    if (!this.savedPlaybookPercentages || !this.state) {
      console.log('⚠️ [PLAYBOOKS] Cannot load percentages: savedPlaybookPercentages=', this.savedPlaybookPercentages, 'state=', !!this.state);
      return;
    }
    
    try {
      const percentages = this.savedPlaybookPercentages;
      console.log('🔍 [PLAYBOOKS] Loading percentages from API:', percentages);
      
      // ✅ SS&S FIX: Reset all percentages to 0 first to ensure database is single source of truth
      // This prevents leftover default percentages (100% for first play) from causing totals > 100%
      Object.keys(this.state.sections).forEach(sectionKey => {
        Object.keys(this.state.sections[sectionKey] || {}).forEach(playId => {
          this.state.sections[sectionKey][playId].percentage = 0;
        });
      });
      console.log('✅ [PLAYBOOKS] Reset all percentages to 0 before applying saved values');
      
      let appliedCount = 0;
      
      // Apply motion percentages
      // ✅ FIX: Iterate through ALL plays in playData, not just state sections
      // State sections only contain first 4 plays, but saved percentages include ALL plays
      if (percentages.motion && Object.keys(percentages.motion).length > 0) {
        console.log('🔍 [PLAYBOOKS] Applying motion percentages:', percentages.motion);
        const motionPlays = this.playData.motion || [];
        
        // ✅ FIX: Iterate through ALL motion plays in playData, not just plays in state sections
        motionPlays.forEach((play, index) => {
          if (!play || play.name === 'To Be Added') return;
          
          // Find or create the playId for this play
          const playId = play.id || `motion-${index + 1}`;
          
          // Ensure this play exists in state sections (create if needed)
          if (!this.state.sections.motion[playId]) {
            this.state.sections.motion[playId] = {
              percentage: 0,
              slot: null,
            };
            console.log(`🔧 [PLAYBOOKS] Created state entry for motion play "${play.name}" (id: ${playId})`);
          }
          
          // Apply saved percentage if it exists in database
          if (percentages.motion[play.name] !== undefined) {
            this.state.sections.motion[playId].percentage = percentages.motion[play.name];
            appliedCount++;
            console.log(`✅ [PLAYBOOKS] Applied motion percentage: ${play.name} = ${percentages.motion[play.name]}%`);
          } else {
            // Play exists in database but not in saved percentages - keep at 0
            console.log(`✅ [PLAYBOOKS] Motion play "${play.name}" (id: ${playId}) not in saved percentages, keeping at 0%`);
          }
        });
      } else {
        console.log('⚠️ [PLAYBOOKS] No motion percentages in saved data');
      }
      
      // Apply set play percentages
      // ✅ FIX: Iterate through ALL plays in playData, not just state sections
      // State sections only contain first N plays, but saved percentages include ALL plays
      ['set-play-inside', 'set-play-attack', 'set-play-outside'].forEach(sectionKey => {
        const settingsKey = sectionKey.replace('set-play-', 'set_play_');
        const sectionPercentages = percentages[settingsKey];
        
        if (sectionPercentages && Object.keys(sectionPercentages).length > 0) {
          console.log(`🔍 [PLAYBOOKS] Applying ${settingsKey} percentages:`, sectionPercentages);
          const plays = this.playData[settingsKey] || [];
          
          // ✅ FIX: Iterate through ALL plays in playData, not just plays in state sections
          // This ensures we match all plays from database, not just the first N that were initialized in state
          plays.forEach((play, index) => {
            if (!play || play.name === 'To Be Added') return;
            
            // Find or create the playId for this play
            const playId = play.id || `${sectionKey}-${index + 1}`;
            
            // Ensure this play exists in state sections (create if needed)
            if (!this.state.sections[sectionKey][playId]) {
              this.state.sections[sectionKey][playId] = {
                percentage: 0,
                slot: null,
              };
              console.log(`🔧 [PLAYBOOKS] Created state entry for ${settingsKey} play "${play.name}" (id: ${playId})`);
            }
            
            // Apply saved percentage if it exists in database
            if (sectionPercentages[play.name] !== undefined) {
              this.state.sections[sectionKey][playId].percentage = sectionPercentages[play.name];
              appliedCount++;
              console.log(`✅ [PLAYBOOKS] Applied ${settingsKey} percentage: ${play.name} = ${sectionPercentages[play.name]}%`);
            } else {
              // Play exists in database but not in saved percentages - keep at 0
              console.log(`✅ [PLAYBOOKS] ${settingsKey} play "${play.name}" (id: ${playId}) not in saved percentages, keeping at 0%`);
            }
          });
        } else {
          console.log(`⚠️ [PLAYBOOKS] No ${settingsKey} percentages in saved data`);
        }
      });
      
      // Apply zone defense percentages
      if (percentages.zone_defense && Object.keys(percentages.zone_defense).length > 0) {
        console.log('🔍 [PLAYBOOKS] Applying zone_defense percentages:', percentages.zone_defense);
        Object.keys(this.state.sections['zone-defense'] || {}).forEach(playId => {
          const play = DEFENSE_PLAY_DATA['zone-defense']?.find(p => p.id === playId);
          if (play) {
            if (percentages.zone_defense[play.name] !== undefined) {
              this.state.sections['zone-defense'][playId].percentage = percentages.zone_defense[play.name];
              appliedCount++;
              console.log(`✅ [PLAYBOOKS] Applied zone_defense percentage: ${play.name} = ${percentages.zone_defense[play.name]}%`);
            } else {
              // Play exists in state but not in saved percentages - already reset to 0 above
              console.log(`✅ [PLAYBOOKS] Zone defense play "${play.name}" (id: ${playId}) not in saved percentages, keeping at 0%`);
            }
          }
        });
      } else {
        console.log('⚠️ [PLAYBOOKS] No zone_defense percentages in saved data');
      }
      
      // Apply man defense percentages
      if (percentages.man_defense && Object.keys(percentages.man_defense).length > 0) {
        console.log('🔍 [PLAYBOOKS] Applying man_defense percentages:', percentages.man_defense);
        Object.keys(this.state.sections['man-defense'] || {}).forEach(playId => {
          const play = DEFENSE_PLAY_DATA['man-defense']?.find(p => p.id === playId);
          if (play) {
            if (percentages.man_defense[play.name] !== undefined) {
              this.state.sections['man-defense'][playId].percentage = percentages.man_defense[play.name];
              appliedCount++;
              console.log(`✅ [PLAYBOOKS] Applied man_defense percentage: ${play.name} = ${percentages.man_defense[play.name]}%`);
            } else {
              // Play exists in state but not in saved percentages - already reset to 0 above
              console.log(`✅ [PLAYBOOKS] Man defense play "${play.name}" (id: ${playId}) not in saved percentages, keeping at 0%`);
            }
          }
        });
      } else {
        console.log('⚠️ [PLAYBOOKS] No man_defense percentages in saved data');
      }
      
      console.log(`✅ [PLAYBOOKS] Applied ${appliedCount} saved percentages from API to state`);
    } catch (error) {
      console.error('❌ Error loading playbook percentages from API:', error);
    }
  }
  
  async loadSlotAssignmentsFromAPI() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      // Check multiple possible team_id parameter names (matching loadAndApplySlotAssignments pattern)
      let teamId = urlParams.get('team_id') || 
                   urlParams.get('user_team_id') || 
                   urlParams.get('home_id') || 
                   urlParams.get('away_id');
      let gameId = urlParams.get('game_id');
      if (!gameId && mode === 'single' && typeof localStorage !== 'undefined') {
        gameId = localStorage.getItem('game_id');
      }
      const tournamentId = urlParams.get('tournament_id');
      const franchiseId = urlParams.get('franchise_id');
      
      if (!teamId) {
        console.warn('⚠️ [PLAYBOOKS] No teamId found, cannot load slot assignments');
        return;
      }
      
      const params = new URLSearchParams();
      params.set('mode', mode);
      params.set('team_id', teamId);
      if (mode === 'single' && gameId) {
        params.set('game_id', gameId);
      } else if (mode === 'tournament' && tournamentId) {
        params.set('tournament_id', tournamentId);
      } else if (mode === 'franchise' && franchiseId) {
        params.set('franchise_id', franchiseId);
      }
      
      console.log('🔍 [PLAYBOOKS] Loading slot assignments from API:', params.toString());
      const response = await fetch(`${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`);
      if (response.ok) {
        const data = await response.json();
        console.log('🔍 [PLAYBOOKS] API response for slot assignments:', data);
        
        if (data.slot_assignments && this.state) {
          // Convert slot assignments to use play names if they use playIds
          const convertedAssignments = {};
          Object.keys(data.slot_assignments).forEach(slotNum => {
            const assignment = data.slot_assignments[slotNum];
            if (assignment) {
              // If assignment has playName, use it directly
              // If it only has playId, try to find the play name
              if (assignment.playName) {
                convertedAssignments[slotNum] = assignment;
              } else if (assignment.playId) {
                // Try to find play name from playId
                let playName = null;
                const allPlays = [
                  ...(this.playData.motion || []),
                  ...(this.playData.set_play_inside || []),
                  ...(this.playData.set_play_attack || []),
                  ...(this.playData.set_play_outside || [])
                ];
                const play = allPlays.find(p => p.id === assignment.playId);
                if (play) {
                  playName = play.name;
                }
                convertedAssignments[slotNum] = {
                  ...assignment,
                  playName: playName || assignment.playId
                };
              } else {
                convertedAssignments[slotNum] = assignment;
              }
            }
          });
          
          this.state.slotAssignments = convertedAssignments;
          console.log('✅ [PLAYBOOKS] Loaded slot assignments:', this.state.slotAssignments);
          
          // Apply slot assignments to section state (for non-motion plays)
          Object.keys(this.state.slotAssignments).forEach(slotNum => {
            const assignment = this.state.slotAssignments[slotNum];
            if (assignment && assignment.section !== 'motion') {
              // Find play by name in the section
              const section = this.state.sections[assignment.section];
              if (section) {
                const playId = Object.keys(section).find(id => {
                  const play = this.playData[assignment.section.replace('set-play-', 'set_play_')]?.find(p => p.id === id);
                  return play && play.name === assignment.playName;
                });
                if (playId && section[playId]) {
                  section[playId].slot = parseInt(slotNum);
                }
              }
            }
          });
        } else {
          console.log('⚠️ [PLAYBOOKS] No slot_assignments in API response or state not initialized');
        }
        
        if (data.motion_dropdowns && this.state) {
          // Merge API motion dropdowns with state (API takes precedence)
          this.state.motionDropdowns = { ...this.state.motionDropdowns, ...data.motion_dropdowns };
          console.log('✅ [PLAYBOOKS] Loaded motion dropdowns:', this.state.motionDropdowns);
        }
      } else {
        console.error('❌ [PLAYBOOKS] Failed to load slot assignments:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('❌ Error loading slot assignments from API:', error);
    }
  }
  
  // ✅ MIGRATION (Task 6.2): Removed saveState() - settings are saved to database only
  // No need for localStorage persistence since database is single source of truth
  async saveState() {
    // No-op: Settings are saved to database via savePlaybookSettings()
    // This method is kept for backward compatibility but does nothing
  }
  
  renderAll() {
    // Render all sections (offense and defense)
    const sections = [
      'motion',
      'set-play-inside',
      'set-play-attack',
      'set-play-outside',
      'man-defense',
      'zone-defense'
    ];
    
    sections.forEach(sectionKey => {
      this.renderSection(sectionKey);
    });
    this.renderAssignedPlays();
    this.updateAllTotals();
  }
  
  renderSection(sectionKey) {
    const container = document.getElementById(`${sectionKey}-rows`);
    if (!container) return;
    
    let plays = [];
    const isOffenseSection = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'].includes(sectionKey);
    
    // Get plays based on section
    if (sectionKey === 'motion') {
      const motionPlays = this.playData.motion || [];
      // Filter by position FIRST (for offense sections), then fill to 4 slots
      if (isOffenseSection) {
        const filteredPlays = motionPlays.filter(play => {
          if (play.name === 'To Be Added') return true; // Always include placeholders
          const playDatabaseId = play.play_id;
          if (!playDatabaseId) return false;
          return this.shouldShowPlay(playDatabaseId);
        });
        for (let i = 0; i < 4; i++) {
          plays.push(i < filteredPlays.length ? filteredPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      } else {
        for (let i = 0; i < 4; i++) {
          plays.push(i < motionPlays.length ? motionPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      }
    } else if (sectionKey === 'set-play-inside') {
      const setPlays = this.playData.set_play_inside || [];
      // Filter by position FIRST (for offense sections), then fill to 3 slots
      if (isOffenseSection) {
        const filteredPlays = setPlays.filter(play => {
          if (play.name === 'To Be Added') return true; // Always include placeholders
          const playDatabaseId = play.play_id;
          if (!playDatabaseId) return false;
          return this.shouldShowPlay(playDatabaseId);
        });
        for (let i = 0; i < 3; i++) {
          plays.push(i < filteredPlays.length ? filteredPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      } else {
        for (let i = 0; i < 3; i++) {
          plays.push(i < setPlays.length ? setPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      }
    } else if (sectionKey === 'set-play-attack') {
      const setPlays = this.playData.set_play_attack || [];
      // Filter by position FIRST (for offense sections), then fill to 3 slots
      if (isOffenseSection) {
        const filteredPlays = setPlays.filter(play => {
          if (play.name === 'To Be Added') return true; // Always include placeholders
          const playDatabaseId = play.play_id;
          if (!playDatabaseId) return false;
          return this.shouldShowPlay(playDatabaseId);
        });
        for (let i = 0; i < 3; i++) {
          plays.push(i < filteredPlays.length ? filteredPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      } else {
        for (let i = 0; i < 3; i++) {
          plays.push(i < setPlays.length ? setPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      }
    } else if (sectionKey === 'set-play-outside') {
      const setPlays = this.playData.set_play_outside || [];
      // Filter by position FIRST (for offense sections), then fill to 3 slots
      if (isOffenseSection) {
        const filteredPlays = setPlays.filter(play => {
          if (play.name === 'To Be Added') return true; // Always include placeholders
          const playDatabaseId = play.play_id;
          if (!playDatabaseId) return false;
          return this.shouldShowPlay(playDatabaseId);
        });
        for (let i = 0; i < 3; i++) {
          plays.push(i < filteredPlays.length ? filteredPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      } else {
        for (let i = 0; i < 3; i++) {
          plays.push(i < setPlays.length ? setPlays[i] : TO_BE_ADDED_PLACEHOLDER);
        }
      }
    } else {
      // Defense plays (hardcoded) - not filtered by position
      plays = DEFENSE_PLAY_DATA[sectionKey] || [];
    }
    
    container.innerHTML = '';
    
    plays.forEach((play, index) => {
      // Generate play ID if it's a placeholder
      let playId = play.id || (sectionKey === 'motion' ? `motion-${index + 1}` : `${sectionKey}-${index + 1}`);
      // For "To Be Added" placeholders, use unique ID matching state initialization
      if (play.name === 'To Be Added') {
        playId = sectionKey === 'motion' ? `motion-tba-${index + 1}` : `${sectionKey}-tba-${index + 1}`;
      }
      
      // Position filtering already done above, so just log for debugging
      if (isOffenseSection && play.name !== 'To Be Added') {
        const playDatabaseId = play.play_id;
        console.log(`🔍 [RENDER SECTION] Rendering play "${play.name}" (play_id: ${playDatabaseId})`);
      }
      
      const playData = this.state.sections[sectionKey][playId] || { percentage: 0, slot: null };
      const row = this.createPlayRow(sectionKey, { ...play, id: playId }, playData);
      container.appendChild(row);
    });
  }
  
  createPlayRow(sectionKey, play, playData) {
    const row = document.createElement('div');
    row.className = 'playbook-row';
    row.dataset.section = sectionKey;
    row.dataset.playId = play.id;
    
    // Column 1: Play Name | Percentage Input
    const column1 = document.createElement('div');
    column1.className = 'row-column-1';
    
    const label = document.createElement('span');
    label.className = 'row-label';
    
    // Make play name clickable (except for "To Be Added")
    if (play.name !== 'To Be Added') {
      const playLink = document.createElement('a');
      playLink.textContent = play.name;
      playLink.href = '#';
      playLink.style.color = 'inherit';
      playLink.style.textDecoration = 'none';
      playLink.style.cursor = 'pointer';
      playLink.addEventListener('click', (e) => {
        e.preventDefault();
        this.navigateToPlayDetails(play.name);
      });
      label.appendChild(playLink);
    } else {
      label.textContent = play.name;
      label.style.fontStyle = 'italic';
      label.style.opacity = '0.6';
    }
    
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'percentage-input';
    input.min = '0';
    input.max = '100';
    input.value = playData.percentage || 0;
    
    // Disable input for "To Be Added" placeholders
    if (play.name === 'To Be Added') {
      input.disabled = true;
      input.style.opacity = '0.5';
      input.style.cursor = 'not-allowed';
    } else {
      input.addEventListener('input', (e) => {
        this.handlePercentageChange(sectionKey, play.id, e.target.value);
      });
      input.addEventListener('blur', () => {
        this.validateAndUpdate();
      });
    }
    
    column1.appendChild(label);
    column1.appendChild(input);
    
    // Column 2: Dropdown (Motion only) | Slot Controls (Motion + Set Plays)
    const column2 = document.createElement('div');
    column2.className = 'row-column-2';
    
    // Motion dropdown (only for motion section)
    if (sectionKey === 'motion') {
      const dropdown = document.createElement('select');
      dropdown.className = 'motion-dropdown';
      dropdown.dataset.playId = play.id; // Store playId for later reference
      
      // Add "-" as default option (explicit unselected state)
      const defaultOption = document.createElement('option');
      defaultOption.value = '-';
      defaultOption.textContent = '-';
      dropdown.appendChild(defaultOption);
      
      // Add Inside, Attack, Outside options
      ['Inside', 'Attack', 'Outside'].forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        dropdown.appendChild(option);
      });
      
      // Set current value (default to "-" if not set)
      const currentValue = this.state.motionDropdowns[play.id];
      dropdown.value = currentValue || '-';
      
      // Ensure state has entry (even if "-") so it persists
      if (!this.state.motionDropdowns[play.id]) {
        this.state.motionDropdowns[play.id] = '-';
      }
      
      // Disable dropdown for "To Be Added" placeholders
      if (play.name === 'To Be Added') {
        dropdown.disabled = true;
        dropdown.style.opacity = '0.5';
        dropdown.style.cursor = 'not-allowed';
      } else {
        dropdown.addEventListener('change', (e) => {
          this.handleMotionDropdownChange(play.id, e.target.value, dropdown);
        });
      }
      column2.appendChild(dropdown);
    } else {
      // Empty spacer for set plays to align slot controls
      const spacer = document.createElement('div');
      spacer.style.width = '80px'; // Match dropdown width
      column2.appendChild(spacer);
    }
    
    // Slot controls (offense only)
    const slotControls = document.createElement('div');
    slotControls.className = 'slot-controls';
    
    if (['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'].includes(sectionKey)) {
      for (let i = 1; i <= 6; i++) {
        const pill = document.createElement('button');
        pill.className = 'slot-pill';
        pill.textContent = i;
        pill.dataset.slot = i;
        
        // Check if this slot is assigned to this play (check all dropdown variants for motion)
        const isAssigned = this.isSlotAssignedToPlay(i, sectionKey, play.id);
        if (isAssigned) {
          pill.classList.add('assigned');
          // Show badge with the dropdown value that this slot is assigned to
          if (sectionKey === 'motion') {
            const assignment = this.state.slotAssignments[i];
            if (assignment && assignment.playId === play.id) {
              const badge = document.createElement('span');
              badge.className = 'slot-badge';
              badge.textContent = assignment.dropdown[0]; // I, A, or O
              // Add color class based on dropdown value
              if (assignment.dropdown === 'Inside') {
                badge.classList.add('inside');
              } else if (assignment.dropdown === 'Attack') {
                badge.classList.add('attack');
              } else if (assignment.dropdown === 'Outside') {
                badge.classList.add('outside');
              }
              pill.appendChild(badge);
            }
          }
        }
        
        // Disable slot assignment for "To Be Added" placeholders
        if (play.name === 'To Be Added') {
          pill.disabled = true;
          pill.style.opacity = '0.5';
          pill.style.cursor = 'not-allowed';
        } else {
          pill.addEventListener('click', () => {
            this.handleSlotClick(i, sectionKey, play.id);
          });
        }
        
        slotControls.appendChild(pill);
      }
    }
    
    column2.appendChild(slotControls);
    
    row.appendChild(column1);
    row.appendChild(column2);
    
    return row;
  }
  
  isSlotAssignedToPlay(slotNumber, sectionKey, playId) {
    const assignment = this.state.slotAssignments[slotNumber];
    if (!assignment) return false;
    
    // For motion, check if slot is assigned to this play (regardless of current dropdown)
    // The badge will show which dropdown variant it's assigned to
    if (sectionKey === 'motion') {
      return assignment.section === 'motion' && assignment.playId === playId;
    }
    
    return assignment.section === sectionKey && assignment.playId === playId;
  }
  
  handleMotionDropdownChange(playId, dropdownValue, dropdownElement) {
    // Update state
    this.state.motionDropdowns[playId] = dropdownValue;
    
    // Update dropdown element directly to ensure UI reflects change immediately
    if (dropdownElement) {
      dropdownElement.value = dropdownValue;
    } else {
      // Fallback: find dropdown by playId and update it
      const dropdown = document.querySelector(`.motion-dropdown[data-play-id="${playId}"]`) || 
                       document.querySelector(`.motion-dropdown[data-playId="${playId}"]`);
      if (dropdown) {
        dropdown.value = dropdownValue;
      }
    }
    
    // Don't change existing slot assignments - they stay with their original dropdown variant
    // Just re-render to update the UI (badges will show correct variant)
    
    this.renderSection('motion');
    this.renderAssignedPlays();
    this.markUnsavedChanges();
  }
  
  handlePercentageChange(sectionKey, playId, value) {
    const numValue = Math.max(0, Math.min(100, parseInt(value) || 0));
    this.state.sections[sectionKey][playId].percentage = numValue;
    
    // Disable Even Distribution toggle if user manually edits
    if (this.evenDistributionEnabled[sectionKey]) {
      this.evenDistributionEnabled[sectionKey] = false;
      this.updateEvenDistributionButton(sectionKey);
      // Update "Even Distribution - All" button state since one section was disabled
      this.updateEvenDistributionAllButton();
      // Set flag to false (user's last action was manual edit)
      this.evenDistributionAllFlag = false;
    }
    
    this.updateSectionTotal(sectionKey);
    this.updateSubmitButton();
    this.markUnsavedChanges();
  }
  
  navigateToPlayDetails(playName) {
    // ✅ SS&S: No need to save to localStorage - database is single source of truth
    // Settings will be loaded fresh from database when user returns
    
    // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
    const helper = window.TimeoutNavigationHelper;
    if (!helper) {
      console.error('❌ [PLAYBOOKS] TimeoutNavigationHelper not loaded!');
      return;
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const currentGameId = helper.getGameId(urlParams);
    const resumeFromTimeout = helper.getResumeFromTimeout(urlParams);
    const currentQuarter = parseInt(urlParams.get('quarter'), 10) || 1;
    const myTeamSide = urlParams.get('my_team');
    
    // Build lineup object from URL params
    const lineup = {};
    if (myTeamSide) {
      ['pg', 'sg', 'sf', 'pf', 'c'].forEach(pos => {
        const paramKey = `${myTeamSide}_${pos}`;
        const playerId = urlParams.get(paramKey);
        if (playerId) {
          lineup[pos.toUpperCase()] = playerId;
        }
      });
    }
    
    // ✅ SS&S: Use TimeoutNavigationHelper to preserve all game context (including resume_from_timeout and clock)
    const params = helper.buildGameNavigationParams({
      sourceParams: urlParams,
      targetQuarter: currentQuarter,
      gameId: currentGameId,
      resumeFromTimeout: resumeFromTimeout,
      lineup: lineup,
      myTeamSide: myTeamSide
    });
    
    // Add play-specific parameter
    params.set('play_name', playName);
    
    // ✅ SS&S: Explicitly set backTo parameter so play-details knows where to navigate back to
    // This makes the back button truly dynamic and future-proof
    params.set('backTo', 'playbooks.html');
    
    // Preserve 'from' parameter if it exists (for playbooks' own back navigation)
    const from = urlParams.get('from');
    if (from) {
      params.set('from', from);
    }
    
    window.location.href = `/play-details.html?${params.toString()}`;
  }
  
  // ✅ SS&S: Removed saveStateToLocalStorage() - database is single source of truth
  // UI state (position filters, even distribution toggles) is saved separately via savePositionFilterSelections()

  handleSlotClick(slotNumber, sectionKey, playId) {
    const dropdown = sectionKey === 'motion' 
      ? (this.state.motionDropdowns[playId] || 'Inside')
      : null;
    
    // Check if this exact combination is already assigned
    const assignment = this.state.slotAssignments[slotNumber];
    const isCurrentlyAssigned = assignment &&
      assignment.section === sectionKey &&
      assignment.playId === playId &&
      (sectionKey !== 'motion' || assignment.dropdown === dropdown);
    
    if (isCurrentlyAssigned) {
      // Unassign
      delete this.state.slotAssignments[slotNumber];
      // Clear slot reference for non-motion plays
      if (sectionKey !== 'motion') {
        this.state.sections[sectionKey][playId].slot = null;
      }
    } else {
      // Assign (will auto-unassign from previous via assignSlot)
      this.state.assignSlot(slotNumber, sectionKey, playId, dropdown);
    }
    
    // Re-render affected sections
    this.renderSection(sectionKey);
    // If unassigning, also re-render the section that previously had this slot
    if (assignment && assignment.section !== sectionKey) {
      this.renderSection(assignment.section);
    }
    this.renderAssignedPlays();
    this.markUnsavedChanges();
  }
  
  updateSectionTotal(sectionKey) {
    const total = this.state.getSectionTotal(sectionKey);
    const totalEl = document.getElementById(`${sectionKey}-total`);
    const errorEl = document.getElementById(`${sectionKey}-error`);
    
    if (totalEl) {
      totalEl.textContent = total;
      totalEl.classList.toggle('warning', total !== 100);
    }
    
    if (errorEl) {
      if (total > 100) {
        const over = total - 100;
        errorEl.textContent = `This section must total 100%. You're over by ${over}%.`;
      } else {
        errorEl.textContent = '';
      }
    }
    
    // Update section visual state
    const sectionEl = document.querySelector(`[data-section="${sectionKey}"]`);
    if (sectionEl) {
      sectionEl.classList.toggle('section-warning', total !== 100);
    }
  }
  
  updateAllTotals() {
    Object.keys(this.state.sections).forEach(sectionKey => {
      this.updateSectionTotal(sectionKey);
    });
  }
  
  validateAndUpdate() {
    // Clamp all percentages to valid range
    Object.keys(this.state.sections).forEach(sectionKey => {
      Object.keys(this.state.sections[sectionKey]).forEach(playId => {
        const playData = this.state.sections[sectionKey][playId];
        playData.percentage = Math.max(0, Math.min(100, playData.percentage || 0));
      });
    });
    
    this.renderAll();
    this.updateSubmitButton();
    this.debouncedSave();
  }
  
  updateSubmitButton() {
    const isValid = this.state.areAllSectionsValid();
    const submitBtn = document.getElementById('submit-btn');
    const helperText = document.getElementById('submit-helper');
    
    if (submitBtn) {
      submitBtn.disabled = !isValid;
    }
    
    if (helperText) {
      helperText.style.display = isValid ? 'none' : 'block';
    }
  }
  
  renderAssignedPlays() {
    const container = document.getElementById('assigned-plays-list');
    if (!container) return;
    
    container.innerHTML = '';
    
    for (let i = 1; i <= 6; i++) {
      const item = document.createElement('div');
      item.className = 'assigned-play-item';
      
      const label = document.createElement('span');
      label.className = 'assigned-play-label';
      label.textContent = `${i}:`;
      
      const name = document.createElement('span');
      name.className = 'assigned-play-name';
      const playName = this.state.getAssignedPlayName(i, this.playData);
      name.textContent = playName || 'Unassigned';
      if (!playName) {
        name.classList.add('unassigned');
      }
      
      item.appendChild(label);
      item.appendChild(name);
      container.appendChild(item);
    }
  }
  
  attachEventListeners() {
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        this.handleSubmit();
      });
    }
    
    // Even Distribution buttons
    const evenDistributionBtns = document.querySelectorAll('.even-distribution-btn');
    evenDistributionBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const sectionKey = e.target.dataset.section;
        this.handleEvenDistribution(sectionKey);
      });
    });
    
    // Even Distribution - All button (for offense sections)
    const evenDistributionAllBtn = document.getElementById('even-distribution-all-btn');
    if (evenDistributionAllBtn) {
      evenDistributionAllBtn.addEventListener('click', () => {
        this.handleEvenDistributionAll();
      });
    }
    
    const backBtn = document.getElementById('back-btn');
    if (backBtn) {
      // ✅ Update back button text based on where user came from
      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get('from');
      const mode = urlParams.get('mode') || 'single';
      
      // Check if from command center (FCC/TCC)
      const isFromCommandCenter = from === 'command_center' || 
                                   from === 'tournament-command-center' || 
                                   from === 'franchise-command-center' ||
                                   (!from && (mode === 'tournament' || mode === 'franchise'));
      
      if (isFromCommandCenter) {
        backBtn.textContent = 'Back To Locker Room';
      } else if (from === 'lineup') {
        backBtn.textContent = 'Back To Lineup';
      } else {
        // Default fallback
        backBtn.textContent = 'Back';
      }
      
      backBtn.addEventListener('click', () => {
        this.handleBack();
      });
    }
    
    // Position filter button listeners
    const positionButtons = document.querySelectorAll('.position-filter-btn');
    positionButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        this.handlePositionFilterClick(btn);
      });
    });
  }
  
  handleEvenDistribution(sectionKey) {
    // Toggle Even Distribution for this section
    this.evenDistributionEnabled[sectionKey] = !this.evenDistributionEnabled[sectionKey];
    
    if (!this.evenDistributionEnabled[sectionKey]) {
      // Disabling - just update button visual state
      this.updateEvenDistributionButton(sectionKey);
      console.log(`🔍 [EVEN DISTRIBUTION] Disabled for section: ${sectionKey}`);
      this.markUnsavedChanges();
      return;
    }
    
    // Enabling - distribute percentages
    console.log(`🔍 [EVEN DISTRIBUTION] Distributing percentages for section: ${sectionKey}`);
    
    this.distributePercentagesEvenly(sectionKey);
    this.updateEvenDistributionButton(sectionKey);
    this.markUnsavedChanges();
  }
  
  handleEvenDistributionAll() {
    // Apply Even Distribution to all offense sections
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    
    // Check if all sections already have Even Distribution enabled
    const allEnabled = offenseSections.every(sectionKey => this.evenDistributionEnabled[sectionKey]);
    
    if (allEnabled) {
      // Disabling - turn off all offense sections
      console.log('🔍 [EVEN DISTRIBUTION ALL] Disabling for all offense sections');
      offenseSections.forEach(sectionKey => {
        this.evenDistributionEnabled[sectionKey] = false;
        this.updateEvenDistributionButton(sectionKey);
      });
      // Set flag to false
      this.evenDistributionAllFlag = false;
    } else {
      // Enabling - apply Even Distribution to all offense sections
      console.log('🔍 [EVEN DISTRIBUTION ALL] Applying to all offense sections');
      
      offenseSections.forEach(sectionKey => {
        // Enable Even Distribution for this section
        this.evenDistributionEnabled[sectionKey] = true;
        
        // Distribute percentages evenly
        this.distributePercentagesEvenly(sectionKey);
        
        // Update button visual state
        this.updateEvenDistributionButton(sectionKey);
      });
      
      // Set flag to true
      this.evenDistributionAllFlag = true;
    }
    
    // Update the "Even Distribution - All" button visual state
    this.updateEvenDistributionAllButton();
    
    this.markUnsavedChanges();
    console.log('✅ [EVEN DISTRIBUTION ALL] Complete for all offense sections, flag:', this.evenDistributionAllFlag);
  }
  
  updateEvenDistributionAllButton() {
    const button = document.getElementById('even-distribution-all-btn');
    if (!button) return;
    
    // Check if all offense sections have Even Distribution enabled
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    const allEnabled = offenseSections.every(sectionKey => this.evenDistributionEnabled[sectionKey]);
    
    if (allEnabled) {
      button.classList.add('active');
      button.textContent = 'Even Distribution - All ✓';
    } else {
      button.classList.remove('active');
      button.textContent = 'Even Distribution - All';
    }
  }
  
  distributePercentagesEvenly(sectionKey) {
    // ✅ SS&S: First, reset ALL plays in this section to 0 to ensure clean redistribution
    // This ensures no leftover percentages from previous distributions or loaded data
    if (this.state.sections[sectionKey]) {
      Object.keys(this.state.sections[sectionKey]).forEach(playId => {
        this.state.sections[sectionKey][playId].percentage = 0;
      });
    }
    
    // Get all plays in this section (excluding "To Be Added" placeholders)
    let plays = [];
    
    if (sectionKey === 'motion') {
      const motionPlays = this.playData.motion || [];
      plays = motionPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'set-play-inside') {
      const setPlays = this.playData.set_play_inside || [];
      plays = setPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'set-play-attack') {
      const setPlays = this.playData.set_play_attack || [];
      plays = setPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'set-play-outside') {
      const setPlays = this.playData.set_play_outside || [];
      plays = setPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'man-defense' || sectionKey === 'zone-defense') {
      plays = DEFENSE_PLAY_DATA[sectionKey] || [];
    }
    
    // Filter by position if offense section
    const isOffenseSection = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'].includes(sectionKey);
    if (isOffenseSection) {
      plays = plays.filter(play => {
        const playDatabaseId = play.play_id;
        if (!playDatabaseId) return false;
        return this.shouldShowPlay(playDatabaseId);
      });
    }
    
    if (plays.length === 0) {
      console.warn(`⚠️ [EVEN DISTRIBUTION] No plays found for section: ${sectionKey}`);
      return;
    }
    
    // Calculate base percentage and remainder
    const basePercentage = Math.floor(100 / plays.length);
    const remainder = 100 - (basePercentage * plays.length);
    
    console.log(`📊 [EVEN DISTRIBUTION] ${plays.length} plays, base: ${basePercentage}%, remainder: ${remainder}%`);
    
    // Assign percentages only to visible plays
    plays.forEach((play, index) => {
      // Generate play ID if needed
      let playId = play.id;
      if (!playId) {
        if (sectionKey === 'motion') {
          playId = `motion-${index + 1}`;
        } else if (sectionKey.startsWith('set-play-')) {
          playId = `${sectionKey}-${index + 1}`;
        } else {
          playId = play.id;
        }
      }
      
      // For "To Be Added" placeholders, use unique ID
      if (play.name === 'To Be Added') {
        playId = sectionKey === 'motion' ? `motion-tba-${index + 1}` : `${sectionKey}-tba-${index + 1}`;
      }
      
      // Ensure play exists in state
      if (!this.state.sections[sectionKey][playId]) {
        this.state.sections[sectionKey][playId] = {
          percentage: 0,
          slot: null,
        };
      }
      
      // Assign base percentage
      let percentage = basePercentage;
      
      // Distribute remainder to top plays (one at a time)
      if (index < remainder) {
        percentage += 1;
      }
      
      this.state.sections[sectionKey][playId].percentage = percentage;
      console.log(`  ✅ ${play.name}: ${percentage}%`);
    });
    
    // Re-render section and update totals
    this.renderSection(sectionKey);
    this.updateSectionTotal(sectionKey);
    this.updateSubmitButton();
    
    console.log(`✅ [EVEN DISTRIBUTION] Complete for section: ${sectionKey}`);
  }
  
  updateEvenDistributionButton(sectionKey) {
    const button = document.querySelector(`.even-distribution-btn[data-section="${sectionKey}"]`);
    if (button) {
      if (this.evenDistributionEnabled[sectionKey]) {
        button.classList.add('active');
        button.textContent = 'Even Distribution ✓';
      } else {
        button.classList.remove('active');
        button.textContent = 'Even Distribution';
      }
    }
    
    // Also update "Even Distribution - All" button state when individual sections change
    this.updateEvenDistributionAllButton();
  }
  
  markUnsavedChanges() {
    this.hasUnsavedChanges = true;
  }
  
  handlePositionFilterClick(button) {
    const position = button.dataset.position;
    const isSelected = button.classList.contains('selected');
    
    if (isSelected) {
      // Deselect if already selected
      button.classList.remove('selected');
      this.selectedPositions = this.selectedPositions.filter(p => p !== position);
    } else {
      // If already have 2 selected, remove the oldest (first in array)
      if (this.selectedPositions.length >= 2) {
        const oldestPosition = this.selectedPositions.shift();
        const oldestButton = document.querySelector(`.position-filter-btn[data-position="${oldestPosition}"]`);
        if (oldestButton) {
          oldestButton.classList.remove('selected');
        }
      }
      
      // Add new selection
      button.classList.add('selected');
      this.selectedPositions.push(position);
    }
    
    console.log('🔍 [POSITION FILTER] Selected positions:', this.selectedPositions);
    
    // Save position filter selections to localStorage
    this.savePositionFilterSelections();
    
    // Reset percentages for hidden plays FIRST (before re-rendering)
    // This ensures percentages are cleared before UI updates
    const offenseSections = ['motion', 'set-play-inside', 'set-play-attack', 'set-play-outside'];
    offenseSections.forEach(sectionKey => {
      this.resetHiddenPlayPercentages(sectionKey);
    });
    
    // Re-render all offense sections to apply filtering
    this.renderSection('motion');
    this.renderSection('set-play-inside');
    this.renderSection('set-play-attack');
    this.renderSection('set-play-outside');
    
    // Auto-recalculate percentages if Even Distribution All is enabled
    // If even_distribution_all: true, redistribute among new visible plays when position filters change
    if (this.evenDistributionAllFlag === true) {
      console.log('🔄 [POSITION FILTER] even_distribution_all is true - auto-redistributing among new visible plays');
      offenseSections.forEach(sectionKey => {
        // Ensure even distribution is enabled for this section (it should be if flag is true)
        this.evenDistributionEnabled[sectionKey] = true;
        // Distribute percentages evenly among visible plays (hidden plays already reset)
        this.distributePercentagesEvenly(sectionKey);
        this.updateEvenDistributionButton(sectionKey);
        this.updateSectionTotal(sectionKey);
      });
      // Ensure "Even Distribution - All" button state is correct
      this.updateEvenDistributionAllButton();
    } else {
      // If flag is false, just update section totals (hidden plays already reset)
      offenseSections.forEach(sectionKey => {
        this.updateSectionTotal(sectionKey);
      });
    }
    
    this.updateSubmitButton();
    this.markUnsavedChanges();
  }
  
  resetHiddenPlayPercentages(sectionKey) {
    // Get all plays in this section (excluding "To Be Added" placeholders)
    let allPlays = [];
    
    if (sectionKey === 'motion') {
      const motionPlays = this.playData.motion || [];
      allPlays = motionPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'set-play-inside') {
      const setPlays = this.playData.set_play_inside || [];
      allPlays = setPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'set-play-attack') {
      const setPlays = this.playData.set_play_attack || [];
      allPlays = setPlays.filter(play => play.name !== 'To Be Added');
    } else if (sectionKey === 'set-play-outside') {
      const setPlays = this.playData.set_play_outside || [];
      allPlays = setPlays.filter(play => play.name !== 'To Be Added');
    }
    
    let resetCount = 0;
    
    // Reset percentages for plays that are not visible (don't match current position filters)
    allPlays.forEach((play, index) => {
      const playDatabaseId = play.play_id;
      if (!playDatabaseId) return;
      
      // Check if this play should be visible with current position filters
      const shouldBeVisible = this.shouldShowPlay(playDatabaseId);
      
      if (!shouldBeVisible) {
        // Play is hidden - reset its percentage to 0
        let playId = play.id;
        if (!playId) {
          if (sectionKey === 'motion') {
            playId = `motion-${index + 1}`;
          } else if (sectionKey.startsWith('set-play-')) {
            playId = `${sectionKey}-${index + 1}`;
          }
        }
        
        // Ensure play exists in state and has a non-zero percentage
        if (this.state.sections[sectionKey][playId]) {
          const oldPercentage = this.state.sections[sectionKey][playId].percentage || 0;
          if (oldPercentage > 0) {
            this.state.sections[sectionKey][playId].percentage = 0;
            resetCount++;
            console.log(`🔄 [POSITION FILTER] Reset percentage from ${oldPercentage}% to 0% for hidden play: ${play.name} (play_id: ${playDatabaseId})`);
          }
        }
      }
    });
    
    if (resetCount > 0) {
      console.log(`🔄 [POSITION FILTER] Reset ${resetCount} hidden play(s) in section "${sectionKey}"`);
    }
  }
  
  savePositionFilterSelections() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      const teamId = urlParams.get('team_id') || 
                     urlParams.get('user_team_id') || 
                     urlParams.get('home_id') || 
                     urlParams.get('away_id');
      
      if (!teamId) return;
      
      // Create a unique key for this team/mode combination
      const storageKey = `playbooks_position_filters_${mode}_${teamId}`;
      localStorage.setItem(storageKey, JSON.stringify(this.selectedPositions));
      console.log('💾 [POSITION FILTER] Saved selections to localStorage:', this.selectedPositions);
    } catch (error) {
      console.error('❌ Error saving position filter selections:', error);
    }
  }
  
  loadPositionFilterSelections() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      const teamId = urlParams.get('team_id') || 
                     urlParams.get('user_team_id') || 
                     urlParams.get('home_id') || 
                     urlParams.get('away_id');
      
      if (!teamId) return;
      
      // Create a unique key for this team/mode combination
      const storageKey = `playbooks_position_filters_${mode}_${teamId}`;
      const saved = localStorage.getItem(storageKey);
      
      if (saved) {
        this.selectedPositions = JSON.parse(saved);
        console.log('📂 [POSITION FILTER] Loaded selections from localStorage:', this.selectedPositions);
        
        // Apply selections to UI buttons
        this.selectedPositions.forEach(position => {
          const button = document.querySelector(`.position-filter-btn[data-position="${position}"]`);
          if (button) {
            button.classList.add('selected');
          }
        });
      }
    } catch (error) {
      console.error('❌ Error loading position filter selections:', error);
    }
  }
  
  /**
   * Check if a play should be shown based on selected position filters.
   * Uses union (OR) logic: play must be in ANY selected position array.
   * "Standard" is treated like any other position filter - only shows plays in the Standard list.
   * If no positions selected, hide all plays.
   * 
   * @param {string} playId - The play's database play_id (ObjectId string)
   * @returns {boolean} - True if play should be shown
   */
  shouldShowPlay(playId) {
    // If no positions selected, hide all plays
    if (this.selectedPositions.length === 0) {
      console.log('🔍 [SHOULD SHOW PLAY] No positions selected, hiding play:', playId);
      return false;
    }
    
    // If play_id is missing, hide the play (can't match against filters)
    if (!playId) {
      console.log('🔍 [SHOULD SHOW PLAY] Missing play_id, hiding play');
      return false;
    }
    
    // Union (OR) logic: play must be in ANY selected position array
    // "Standard" is treated like any other position - only shows plays in its list
    if (!this.positionFilters) {
      console.log('🔍 [SHOULD SHOW PLAY] No positionFilters loaded, hiding play:', playId);
      return false;
    }
    
    // Check if play is in any of the selected position arrays
    for (const position of this.selectedPositions) {
      const positionPlayIds = this.positionFilters[position] || [];
      console.log(`🔍 [SHOULD SHOW PLAY] Checking position "${position}": playIds=${JSON.stringify(positionPlayIds)}, looking for playId="${playId}"`);
      if (positionPlayIds.includes(playId)) {
        console.log(`✅ [SHOULD SHOW PLAY] Play "${playId}" found in position "${position}"`);
        return true; // Play found in at least one selected position array
      }
    }
    
    console.log(`❌ [SHOULD SHOW PLAY] Play "${playId}" not found in any selected position arrays`);
    return false; // Play not found in any selected position array
  }
  
  handleBack() {
    // Check if there are unsaved changes and show warning popup
    if (this.hasUnsavedChanges) {
      const suppressWarning = sessionStorage.getItem('playbooks_suppress_warning') === 'true';
      if (!suppressWarning) {
        this.showUnsavedChangesWarning();
        return;
      }
    }
    
    // No unsaved changes or warning suppressed - proceed with navigation
    this.executeBackNavigation();
  }
  
  showUnsavedChangesWarning() {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'playbooks-warning-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    `;
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'playbooks-warning-modal';
    modal.style.cssText = `
      background: #1a1a1a;
      border: 2px solid #ff7a00;
      border-radius: 8px;
      padding: 24px;
      max-width: 500px;
      width: 90%;
      color: #fff;
    `;
    
    // Message
    const message = document.createElement('p');
    message.textContent = "You haven't saved playbook changes.";
    message.style.cssText = `
      font-size: 1.125rem;
      margin-bottom: 20px;
      font-weight: 600;
    `;
    
    // Checkbox
    const checkboxContainer = document.createElement('div');
    checkboxContainer.style.cssText = 'margin-bottom: 20px;';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = 'playbooks-suppress-warning';
    checkbox.style.cssText = 'margin-right: 8px;';
    
    const checkboxLabel = document.createElement('label');
    checkboxLabel.htmlFor = 'playbooks-suppress-warning';
    checkboxLabel.textContent = "Don't show this message again";
    checkboxLabel.style.cssText = 'color: #fff; cursor: pointer;';
    
    checkboxContainer.appendChild(checkbox);
    checkboxContainer.appendChild(checkboxLabel);
    
    // Buttons container
    const buttonsContainer = document.createElement('div');
    buttonsContainer.style.cssText = `
      display: flex;
      gap: 12px;
      justify-content: flex-end;
    `;
    
    // Save Playbooks button
    const submitBtn = document.createElement('button');
    submitBtn.textContent = 'Save Playbooks';
    submitBtn.style.cssText = `
      padding: 10px 20px;
      background: #ff7a00;
      color: #000;
      border: none;
      border-radius: 4px;
      font-weight: 600;
      cursor: pointer;
    `;
    submitBtn.addEventListener('click', async () => {
      if (checkbox.checked) {
        sessionStorage.setItem('playbooks_suppress_warning', 'true');
      }
      overlay.remove();
      await this.handleSubmit();
      // After successful submit, navigate back
      if (!this.hasUnsavedChanges) {
        this.executeBackNavigation();
      }
    });
    
    // Leave Without Submitting button
    const leaveBtn = document.createElement('button');
    leaveBtn.textContent = 'Leave Without Submitting';
    leaveBtn.style.cssText = `
      padding: 10px 20px;
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 4px;
      font-weight: 600;
      cursor: pointer;
    `;
    leaveBtn.addEventListener('click', () => {
      if (checkbox.checked) {
        sessionStorage.setItem('playbooks_suppress_warning', 'true');
      }
      
      // Clear full state from localStorage
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      const teamId = urlParams.get('team_id') || 
                     urlParams.get('user_team_id') || 
                     urlParams.get('home_id') || 
                     urlParams.get('away_id');
      
      if (teamId) {
        const storageKey = `playbooks_full_state_${mode}_${teamId}`;
        localStorage.removeItem(storageKey);
      }
      
      overlay.remove();
      this.hasUnsavedChanges = false;
      this.executeBackNavigation();
    });
    
    buttonsContainer.appendChild(submitBtn);
    buttonsContainer.appendChild(leaveBtn);
    
    modal.appendChild(message);
    modal.appendChild(checkboxContainer);
    modal.appendChild(buttonsContainer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
  }
  
  executeBackNavigation() {
    // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
    const helper = window.TimeoutNavigationHelper;
    if (!helper) {
      console.error('❌ [PLAYBOOKS] TimeoutNavigationHelper not loaded!');
      return;
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const from = urlParams.get('from');
    const mode = urlParams.get('mode') || 'single';
    
    console.log('🔍 [PLAYBOOKS BACK] Navigation params:', {
      from,
      mode,
      franchise_id: urlParams.get('franchise_id'),
      tournament_id: urlParams.get('tournament_id'),
      team_id: urlParams.get('team_id'),
      allParams: Object.fromEntries(urlParams.entries())
    });
    
    const currentGameId = helper.getGameId(urlParams);
    const resumeFromTimeout = helper.getResumeFromTimeout(urlParams);
    const currentQuarter = parseInt(urlParams.get('quarter'), 10) || 1;
    const myTeamSide = urlParams.get('my_team');
    
    // Build lineup object from URL params
    const lineup = {};
    if (myTeamSide) {
      ['pg', 'sg', 'sf', 'pf', 'c'].forEach(pos => {
        const paramKey = `${myTeamSide}_${pos}`;
        const playerId = urlParams.get(paramKey);
        if (playerId) {
          lineup[pos.toUpperCase()] = playerId;
        }
      });
    }
    
    // Determine where to navigate back based on 'from' parameter
    if (from === 'tournament-command-center') {
      // Navigate back to Tournament Command Center
      console.log('✅ [PLAYBOOKS BACK] Navigating to Tournament Command Center');
      const tournamentId = urlParams.get('tournament_id');
      const userTeamId = urlParams.get('team_id') || urlParams.get('user_team_id');
      
      // For command centers, we don't need game context, just mode-specific params
      const params = new URLSearchParams();
      if (tournamentId) params.set('tournament_id', tournamentId);
      if (userTeamId) params.set('user_team_id', userTeamId);
      
      window.location.href = `/tournament.html?${params.toString()}`;
      return;
    }
    
    // Fallback: If mode is tournament but no 'from' parameter, assume tournament-command-center
    if (mode === 'tournament' && !from) {
      console.log('⚠️ [PLAYBOOKS BACK] No "from" parameter, but mode is tournament - assuming tournament-command-center');
      const tournamentId = urlParams.get('tournament_id');
      const userTeamId = urlParams.get('team_id') || urlParams.get('user_team_id');
      
      const params = new URLSearchParams();
      if (tournamentId) params.set('tournament_id', tournamentId);
      if (userTeamId) params.set('user_team_id', userTeamId);
      
      window.location.href = `/tournament.html?${params.toString()}`;
      return;
    }
    
    if (from === 'franchise-command-center') {
      // Navigate back to Franchise Command Center
      const franchiseId = urlParams.get('franchise_id');
      const teamId = urlParams.get('team_id') || urlParams.get('user_team_id'); // Support both for backward compatibility
      
      console.log('✅ [PLAYBOOKS BACK] Navigating to Franchise Command Center');
      
      // For command centers, we don't need game context, just mode-specific params
      const params = new URLSearchParams();
      params.set('mode', 'franchise'); // Always include mode for consistency
      if (franchiseId) params.set('franchise_id', franchiseId);
      if (teamId) params.set('team_id', teamId); // Use team_id (ObjectId), not user_team_name
      
      window.location.href = `/franchise-command-center.html?${params.toString()}`;
      return;
    }
    
    // Fallback: If mode is franchise but no 'from' parameter, assume franchise-command-center
    if (mode === 'franchise' && !from) {
      console.log('⚠️ [PLAYBOOKS BACK] No "from" parameter, but mode is franchise - assuming franchise-command-center');
      const franchiseId = urlParams.get('franchise_id');
      const teamId = urlParams.get('team_id') || urlParams.get('user_team_id'); // Support both for backward compatibility
      
      const params = new URLSearchParams();
      params.set('mode', 'franchise'); // Always include mode for consistency
      if (franchiseId) params.set('franchise_id', franchiseId);
      if (teamId) params.set('team_id', teamId); // Use team_id (ObjectId), not user_team_name
      
      window.location.href = `/franchise-command-center.html?${params.toString()}`;
      return;
    }
    
    // ✅ FIX: Check if from lineup - go back to Lineup Selection screen
    if (from === 'lineup') {
      console.log('✅ [PLAYBOOKS BACK] Navigating to Lineup Selection screen');
      
      // ✅ SS&S: Use TimeoutNavigationHelper to preserve all game context
      const params = helper.buildGameNavigationParams({
        sourceParams: urlParams,
        targetQuarter: currentQuarter,
        gameId: currentGameId,
        resumeFromTimeout: resumeFromTimeout,
        lineup: lineup,
        myTeamSide: myTeamSide
      });
      
      window.location.href = `/set-lineup.html?${params.toString()}`;
      return;
    }
    
    // Default: go back to game-plan (from === 'game-plan' or no 'from' parameter)
    console.log('✅ [PLAYBOOKS BACK] Navigating to Game Plan (default)');
    
    // ✅ SS&S: Use TimeoutNavigationHelper to preserve all game context (including resume_from_timeout and clock)
    const params = helper.buildGameNavigationParams({
      sourceParams: urlParams,
      targetQuarter: currentQuarter,
      gameId: currentGameId,
      resumeFromTimeout: resumeFromTimeout,
      lineup: lineup,
      myTeamSide: myTeamSide
    });
    
    // ✅ FIX: Preserve original 'from' parameter if it indicates command center navigation
    // This ensures Game Plan shows correct back button (Back to Locker Room vs Back to Lineup)
    const originalFrom = urlParams.get('from');
    if (originalFrom === 'command_center' || originalFrom === 'tournament-command-center' || originalFrom === 'franchise-command-center') {
      // Preserve original command center source
      params.set('from', originalFrom);
      console.log('✅ [PLAYBOOKS BACK] Preserving original from parameter:', originalFrom);
    } else if (!currentGameId && (mode === 'tournament' || mode === 'franchise')) {
      // If no game_id and in tournament/franchise mode, likely came from command center
      // Determine which command center based on mode
      if (mode === 'tournament') {
        params.set('from', 'command_center');
      } else if (mode === 'franchise') {
        params.set('from', 'command_center');
      }
      console.log('✅ [PLAYBOOKS BACK] Inferring command center source (no game_id, mode:', mode);
    } else {
      // Otherwise, set to 'playbooks' to indicate we came from Playbooks
      params.set('from', 'playbooks');
    }
    
    window.location.href = `/game-plan.html?${params.toString()}`;
  }
  
  async handleSubmit() {
    if (!this.state.areAllSectionsValid()) {
      return;
    }
    
    // Final validation
    this.validateAndUpdate();
    
    if (!this.state.areAllSectionsValid()) {
      return;
    }
    
    // ✅ MIGRATION (Task 6.2): Save playbook settings to database (single source of truth)
    // No localStorage persistence needed - database is authoritative
    const success = await this.savePlaybookSettings();
    
    if (success) {
      // Clear unsaved changes flag after successful save
      this.hasUnsavedChanges = false;
      this.showToast('Playbooks saved successfully');
    } else {
      this.showToast('Error saving playbooks', true);
    }
  }
  
  async savePlaybookSettings() {
    try {
      // Get URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      // Check multiple possible team_id parameter names (matching loadAndApplySlotAssignments pattern)
      const teamId = urlParams.get('team_id') || 
                     urlParams.get('user_team_id') || 
                     urlParams.get('home_id') || 
                     urlParams.get('away_id');
      // Try to get game_id from URL, fallback to localStorage
      let gameId = urlParams.get('game_id');
      if (!gameId && mode === 'single' && typeof localStorage !== 'undefined') {
        gameId = localStorage.getItem('game_id');
      }
      const tournamentId = urlParams.get('tournament_id');
      const franchiseId = urlParams.get('franchise_id');
      
      if (!teamId) {
        console.error('❌ No team_id found in URL params');
        this.showToast('Error: Team ID not found', true);
        return false;
      }
      
      // For single mode, game_id is required
      if (mode === 'single' && !gameId) {
        console.error('❌ No game_id found in URL params or localStorage for single mode');
        this.showToast('Error: Game ID not found. Please start a game first.', true);
        return false;
      }
      
      // Build playbook settings from state
      const playbookSettings = {
        motion: {},
        set_play_inside: {},
        set_play_attack: {},
        set_play_outside: {},
        zone_defense: {}
      };
      
      // ✅ FIX: Save ALL percentages including 0% (database is single source of truth)
      // Extract motion play percentages (exclude "To Be Added")
      console.log('🔍 [PLAYBOOKS SAVE] Building playbookSettings from state...');
      console.log('🔍 [PLAYBOOKS SAVE] Motion plays in state:', Object.keys(this.state.sections.motion || {}));
      Object.keys(this.state.sections.motion || {}).forEach(playId => {
        const playData = this.state.sections.motion[playId];
        // Find play name from playData
        const play = this.playData.motion?.find(p => p.id === playId);
        if (play && play.name !== 'To Be Added') {
          // Save percentage even if 0 (ensures database is complete source of truth)
          const percentage = playData.percentage || 0;
          playbookSettings.motion[play.name] = percentage;
          console.log(`🔍 [PLAYBOOKS SAVE] Motion: ${play.name} = ${percentage}%`);
        }
      });
      
      // Extract set play percentages (exclude "To Be Added")
      ['set-play-inside', 'set-play-attack', 'set-play-outside'].forEach(sectionKey => {
        const settingsKey = sectionKey.replace('set-play-', 'set_play_');
        const plays = this.playData[settingsKey] || [];
        console.log(`🔍 [PLAYBOOKS SAVE] ${settingsKey} plays in state:`, Object.keys(this.state.sections[sectionKey] || {}));
        
        Object.keys(this.state.sections[sectionKey] || {}).forEach(playId => {
          const playData = this.state.sections[sectionKey][playId];
          // Find play name from playData
          const play = plays.find(p => p.id === playId);
          if (play && play.name !== 'To Be Added') {
            // Save percentage even if 0 (ensures database is complete source of truth)
            const percentage = playData.percentage || 0;
            playbookSettings[settingsKey][play.name] = percentage;
            console.log(`🔍 [PLAYBOOKS SAVE] ${settingsKey}: ${play.name} = ${percentage}%`);
          }
        });
      });
      
      // Extract zone defense percentages (exclude "To Be Added")
      Object.keys(this.state.sections['zone-defense'] || {}).forEach(playId => {
        const playData = this.state.sections['zone-defense'][playId];
        // Find play name from DEFENSE_PLAY_DATA
        const play = DEFENSE_PLAY_DATA['zone-defense']?.find(p => p.id === playId);
        if (play && play.name !== 'To Be Added') {
          // Save percentage even if 0 (ensures database is complete source of truth)
          playbookSettings.zone_defense[play.name] = playData.percentage || 0;
        }
      });
      
      // Include slot assignments and motion dropdowns in playbook settings
      playbookSettings.slot_assignments = this.state.slotAssignments;
      playbookSettings.motion_dropdowns = this.state.motionDropdowns;
      
      // Include man_defense percentages (was missing before)
      playbookSettings.man_defense = {};
      Object.keys(this.state.sections['man-defense'] || {}).forEach(playId => {
        const playData = this.state.sections['man-defense'][playId];
        const play = DEFENSE_PLAY_DATA['man-defense']?.find(p => p.id === playId);
        if (play && play.name !== 'To Be Added') {
          // Save percentage even if 0 (ensures database is complete source of truth)
          playbookSettings.man_defense[play.name] = playData.percentage || 0;
        }
      });
      
      // ✅ NEW: Include even_distribution_all flag (stores user's last action)
      playbookSettings.even_distribution_all = this.evenDistributionAllFlag || false;
      
      console.log('🔍 [PLAYBOOKS SAVE] Final playbookSettings structure:', JSON.stringify(playbookSettings, null, 2));
      console.log('🔍 [PLAYBOOKS] Saving slot assignments:', this.state.slotAssignments);
      console.log('🔍 [PLAYBOOKS] Saving motion dropdowns:', this.state.motionDropdowns);
      console.log('🔍 [PLAYBOOKS] Saving even_distribution_all flag:', playbookSettings.even_distribution_all);
      
      // Build request body
      const requestBody = {
        mode: mode,
        team_id: teamId,
        playbook_settings: playbookSettings
      };
      console.log('🔍 [PLAYBOOKS SAVE] Request body (mode, team_id, franchise_id, tournament_id, game_id):', {
        mode: mode,
        team_id: teamId,
        franchise_id: franchiseId,
        tournament_id: tournamentId,
        game_id: gameId
      });
      
      if (mode === 'single' && gameId) {
        requestBody.game_id = gameId;
      } else if (mode === 'tournament' && tournamentId) {
        requestBody.tournament_id = tournamentId;
      } else if (mode === 'franchise' && franchiseId) {
        requestBody.franchise_id = franchiseId;
      }
      
      // Save to API
      const response = await fetch(API_CONFIG.buildUrl('/api/playbooks'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('✅ [PLAYBOOKS SAVE] Playbook settings saved successfully:', result);
        console.log('✅ [PLAYBOOKS SAVE] Response status:', response.status);
        return true;
      } else {
        const errorText = await response.text();
        console.error('❌ [PLAYBOOKS SAVE] Failed to save playbook settings. Status:', response.status);
        console.error('❌ [PLAYBOOKS SAVE] Error response:', errorText);
        console.error('❌ [PLAYBOOKS SAVE] Request body was:', JSON.stringify(requestBody, null, 2));
        try {
          const error = JSON.parse(errorText);
          console.error('❌ [PLAYBOOKS SAVE] Parsed error:', error);
        } catch (e) {
          console.error('❌ [PLAYBOOKS SAVE] Could not parse error as JSON');
        }
        return false;
      }
    } catch (error) {
      console.error('❌ Error saving playbook settings:', error);
      console.error('❌ Error stack:', error.stack);
      return false;
    }
  }
  
  showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.className = `toast ${isError ? 'error' : ''}`;
    toast.classList.add('show');
    
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  }
  
  debouncedSave() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.saveState();
    }, 500);
  }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // ✅ PHASE 1.1: Validate game_id requirement for single mode on page load
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode') || 'single';
  const gameId = urlParams.get('game_id') || null;
  const quarter = parseInt(urlParams.get('quarter'), 10) || 1;
  const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
  const homeTeam = urlParams.get('home');
  const awayTeam = urlParams.get('away');
  const myTeamSide = urlParams.get('my_team') || 'home';
  
  // ✅ PHASE 1.1: Fail loudly if game_id is required but missing
  // For single mode, game_id is required for ALL quarters (Q1 must be created by init-game)
  // For tournament/franchise mode, game_id is optional (may not exist yet)
  const isGameIdRequired = (mode === 'single') || (quarter > 1) || resumeFromTimeout;
  if (isGameIdRequired && !gameId) {
    const errorMsg = `game_id is required but missing from URL. Mode: ${mode}, Quarter: ${quarter}, Resume from timeout: ${resumeFromTimeout}. Please navigate from the lineup screen with a valid game_id (created by init-game).`;
    console.error(`❌ [PLAYBOOKS] ${errorMsg}`);
    alert(`Error: ${errorMsg}\n\nPlease return to the lineup screen and try again.`);
    // Redirect to lineup screen if possible
    if (homeTeam && awayTeam) {
      const lineupUrl = `/set-lineup.html?home=${encodeURIComponent(homeTeam)}&away=${encodeURIComponent(awayTeam)}&my_team=${encodeURIComponent(myTeamSide)}&mode=${encodeURIComponent(mode)}&quarter=${quarter}`;
      window.location.href = lineupUrl;
    }
    return;
  }
  
  const ui = new PlaybooksUI();
  ui.init();
});

