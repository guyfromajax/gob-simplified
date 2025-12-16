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
    // Initialize motion plays (6 slots max)
    const motionPlays = this.playData.motion || [];
    const motionSlots = 6;
    
    for (let i = 0; i < motionSlots; i++) {
      const play = i < motionPlays.length ? motionPlays[i] : TO_BE_ADDED_PLACEHOLDER;
      const playId = play.id || `motion-${i + 1}`;
      
      this.sections.motion[playId] = {
        percentage: i === 0 ? 100 : 0,
        slot: null,
      };
      
      if (play.name !== 'To Be Added') {
        this.motionDropdowns[playId] = 'Inside';
      }
    }
    
    // Initialize set play sections (2 slots each)
    const setPlaySections = [
      { key: 'set-play-inside', plays: this.playData.set_play_inside || [] },
      { key: 'set-play-attack', plays: this.playData.set_play_attack || [] },
      { key: 'set-play-outside', plays: this.playData.set_play_outside || [] },
    ];
    
    setPlaySections.forEach(({ key, plays }) => {
      for (let i = 0; i < 2; i++) {
        const play = i < plays.length ? plays[i] : TO_BE_ADDED_PLACEHOLDER;
        const playId = play.id || `${key}-${i + 1}`;
        
        this.sections[key][playId] = {
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
        dropdown = this.motionDropdowns[playId] || 'Inside';
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
    if (data.motionDropdowns) this.motionDropdowns = data.motionDropdowns;
  }
}

// ============================================================================
// PERSISTENCE LAYER
// ============================================================================

class PlaybooksPersistence {
  constructor() {
    this.storageKey = 'gob_playbooks';
    this.apiEndpoint = '/api/playbooks'; // Placeholder - can be swapped later
  }
  
  async load() {
    try {
      // Try API first (stubbed for now)
      // const response = await fetch(this.apiEndpoint);
      // if (response.ok) return await response.json();
      
      // Fallback to localStorage
      const stored = localStorage.getItem(this.storageKey);
      return stored ? JSON.parse(stored) : null;
    } catch (error) {
      console.error('Error loading playbooks:', error);
      return null;
    }
  }
  
  async save(data) {
    try {
      // Try API first (stubbed for now)
      // const response = await fetch(this.apiEndpoint, {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(data),
      // });
      // if (response.ok) return true;
      
      // Fallback to localStorage
      localStorage.setItem(this.storageKey, JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Error saving playbooks:', error);
      return false;
    }
  }
}

// ============================================================================
// UI CONTROLLER
// ============================================================================

class PlaybooksUI {
  constructor() {
    this.state = null; // Will be initialized after loading plays
    this.persistence = new PlaybooksPersistence();
    this.debounceTimer = null;
    this.playData = null;
  }
  
  async init() {
    // Load plays from API first
    await this.loadPlays();
    
    // Initialize state with loaded plays
    this.state = new PlaybooksState(this.playData);
    
    // Load saved state (if any)
    await this.loadState();
    
    this.renderAll();
    this.attachEventListeners();
    this.updateSubmitButton();
  }
  
  async loadPlays() {
    try {
      // Get URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const mode = urlParams.get('mode') || 'single';
      const teamId = urlParams.get('team_id') || urlParams.get('home_id') || urlParams.get('away_id');
      const gameId = urlParams.get('game_id');
      const tournamentId = urlParams.get('tournament_id');
      const franchiseId = urlParams.get('franchise_id');
      
      if (!teamId) {
        console.warn('⚠️ No team_id found in URL params, using hardcoded plays');
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
      
      const response = await fetch(`/api/playbooks?${params.toString()}`);
      if (response.ok) {
        const data = await response.json();
        
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
    const saved = await this.persistence.load();
    if (saved) {
      this.state.deserialize(saved);
    }
  }
  
  async saveState() {
    await this.persistence.save(this.state.serialize());
  }
  
  renderAll() {
    Object.keys(PLAY_DATA).forEach(sectionKey => {
      this.renderSection(sectionKey);
    });
    this.renderAssignedPlays();
    this.updateAllTotals();
  }
  
  renderSection(sectionKey) {
    const container = document.getElementById(`${sectionKey}-rows`);
    if (!container) return;
    
    let plays = [];
    
    // Get plays based on section
    if (sectionKey === 'motion') {
      const motionPlays = this.playData.motion || [];
      // Fill to 6 slots
      for (let i = 0; i < 6; i++) {
        plays.push(i < motionPlays.length ? motionPlays[i] : TO_BE_ADDED_PLACEHOLDER);
      }
    } else if (sectionKey === 'set-play-inside') {
      const setPlays = this.playData.set_play_inside || [];
      // Fill to 2 slots
      for (let i = 0; i < 2; i++) {
        plays.push(i < setPlays.length ? setPlays[i] : TO_BE_ADDED_PLACEHOLDER);
      }
    } else if (sectionKey === 'set-play-attack') {
      const setPlays = this.playData.set_play_attack || [];
      // Fill to 2 slots
      for (let i = 0; i < 2; i++) {
        plays.push(i < setPlays.length ? setPlays[i] : TO_BE_ADDED_PLACEHOLDER);
      }
    } else if (sectionKey === 'set-play-outside') {
      const setPlays = this.playData.set_play_outside || [];
      // Fill to 2 slots
      for (let i = 0; i < 2; i++) {
        plays.push(i < setPlays.length ? setPlays[i] : TO_BE_ADDED_PLACEHOLDER);
      }
    } else {
      // Defense plays (hardcoded)
      plays = DEFENSE_PLAY_DATA[sectionKey] || [];
    }
    
    container.innerHTML = '';
    
    plays.forEach((play, index) => {
      // Generate play ID if it's a placeholder
      const playId = play.id || (sectionKey === 'motion' ? `motion-${index + 1}` : `${sectionKey}-${index + 1}`);
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
    label.textContent = play.name;
    
    // Style "To Be Added" differently
    if (play.name === 'To Be Added') {
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
      dropdown.value = this.state.motionDropdowns[play.id] || 'Inside';
      ['Inside', 'Attack', 'Outside'].forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        dropdown.appendChild(option);
      });
      // Disable dropdown for "To Be Added" placeholders
      if (play.name === 'To Be Added') {
        dropdown.disabled = true;
        dropdown.style.opacity = '0.5';
        dropdown.style.cursor = 'not-allowed';
      } else {
        dropdown.addEventListener('change', (e) => {
          this.handleMotionDropdownChange(play.id, e.target.value);
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
  
  handleMotionDropdownChange(playId, dropdownValue) {
    // Update dropdown value (persists the selection)
    this.state.motionDropdowns[playId] = dropdownValue;
    
    // Don't change existing slot assignments - they stay with their original dropdown variant
    // Just re-render to update the UI (badges will show correct variant)
    
    this.renderSection('motion');
    this.renderAssignedPlays();
    this.debouncedSave();
  }
  
  handlePercentageChange(sectionKey, playId, value) {
    const numValue = Math.max(0, Math.min(100, parseInt(value) || 0));
    this.state.sections[sectionKey][playId].percentage = numValue;
    
    this.updateSectionTotal(sectionKey);
    this.updateSubmitButton();
  }
  
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
    this.debouncedSave();
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
    
    // Save
    const success = await this.saveState();
    
    if (success) {
      this.showToast('Saved');
    } else {
      this.showToast('Error saving', true);
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
  const ui = new PlaybooksUI();
  ui.init();
});

