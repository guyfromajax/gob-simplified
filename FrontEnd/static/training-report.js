// Training Report Page JavaScript

const urlParams = new URLSearchParams(window.location.search);
const mode = urlParams.get('mode');
const franchiseId = urlParams.get('franchise_id');
const tournamentId = urlParams.get('tournament_id');
const teamId = urlParams.get('team_id');
const week = parseInt(urlParams.get('week'), 10);

let reportData = null;
let currentView = 'attributes'; // 'attributes' or 'changes'

// Attribute abbreviations mapping
const ATTRIBUTE_NAMES = {
  'SC': 'SC',
  'SH': 'SH',
  'ID': 'ID',
  'OD': 'OD',
  'PS': 'PS',
  'BH': 'BH',
  'RB': 'RB',
  'AG': 'AG',
  'ST': 'ST',
  'ND': 'ND',
  'IQ': 'IQ',
  'FT': 'FT',
  'CH': 'CH'
};

// Team attribute display names
const TEAM_ATTR_NAMES = {
  'shot_threshold': 'Shooting',
  'rebound_modifier': 'Rebounding',
  'offensive_efficiency': 'Offense',
  'defensive_efficiency': 'Defense',
  'fb_efficiency': 'Fast Breaks',
  'pt_efficiency': 'Press/Trap',
  'foul_modifier': 'Aggression',
  'turnover_modifier': 'Discipline',
  'momentum_score': 'Momentum',
  'team_chemistry': 'Team Chemistry',
  'fb_opp_modifier': 'Fast Break Defense',
  'pt_opp_modifier': 'Press/Trap Breaks'
};

// Coaching focus display names
const FOCUS_DISPLAY = {
  'authoritarian': {
    'discipline': 'Authoritarian - Discipline',
    'rebounding': 'Authoritarian - Rebounding',
    'teamwork': 'Authoritarian - Teamwork',
    'execution': 'Authoritarian - Execution'
  },
  'systems-coach': {
    'offense': 'Systems Coach - Offense',
    'defense': 'Systems Coach - Defense',
    'fast-breaks': 'Systems Coach - Fast Breaks',
    'presses-traps': 'Systems Coach - Presses/Traps'
  },
  'player-maximizer': {
    'top-3': 'Player Maximizer - Top 3 Attributes',
    'attributes-4-6': 'Player Maximizer - Attributes 4-6',
    'custom': 'Player Maximizer - Custom',
    'be-opportunistic': 'Player Maximizer - Be Opportunistic'
  },
  'culture-builder': {
    'inspire': 'Culture Builder - Inspire',
    'community': 'Culture Builder - Community Engagement',
    'teamwork': 'Culture Builder - Teamwork',
    'build-confidence': 'Culture Builder - Build Confidence'
  }
};

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
  if (!mode || !teamId || !week) {
    console.error('Missing required URL parameters');
    return;
  }

  // Set up view toggle
  setupViewToggle();
  
  // Set up locker room button
  setupLockerRoomButton();
  
  // Load training report data
  loadTrainingReport();
});

function setupViewToggle() {
  const toggleButtons = document.querySelectorAll('.toggle-btn');
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      toggleButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentView = btn.dataset.view;
      renderPlayersTable();
    });
  });
}

function setupLockerRoomButton() {
  const btn = document.getElementById('locker-room-btn');
  if (!btn) return;
  
  btn.addEventListener('click', () => {
    if (mode === 'franchise') {
      window.location.href = `/static/franchise-command-center.html?franchise_id=${franchiseId}&team_id=${teamId}`;
    } else if (mode === 'tournament') {
      window.location.href = `/static/tournament-command-center.html?tournament_id=${tournamentId}&team_id=${teamId}`;
    }
  });
}

async function loadTrainingReport() {
  try {
    const params = new URLSearchParams({
      mode: mode,
      team_id: teamId,
      week: week
    });
    
    if (franchiseId) params.set('franchise_id', franchiseId);
    if (tournamentId) params.set('tournament_id', tournamentId);
    
    console.log('🔍 [TRAINING REPORT] Loading with params:', Object.fromEntries(params.entries()));
    
    const response = await fetch(`/franchise/training-report?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to load training report: ${response.statusText}`);
    }
    
    reportData = await response.json();
    console.log('🔍 [TRAINING REPORT] Loaded data:', reportData);
    console.log('🔍 [TRAINING REPORT] Players count:', reportData.players?.length || 0);
    console.log('🔍 [TRAINING REPORT] Player changes:', reportData.player_changes);
    
    renderPage();
  } catch (error) {
    console.error('Error loading training report:', error);
    alert('Failed to load training report. Please try again.');
  }
}

function renderPage() {
  if (!reportData) return;
  
  // Render header
  renderHeader();
  
  // Render players table
  renderPlayersTable();
  
  // Render team attributes
  renderTeamAttributes();
}

function renderHeader() {
  document.getElementById('week-number').textContent = reportData.week || '--';
  document.getElementById('upcoming-opponent').textContent = reportData.upcoming_opponent || '--';
  
  const focus = reportData.coaching_focus || {};
  const archetype = focus.archetype || '';
  const subOption = focus.sub_option || '';
  
  let focusText = '--';
  if (archetype && subOption) {
    // Map archetype to full name
    const archetypeMap = {
      'authoritarian': 'Authoritarian',
      'systems-coach': 'Systems Coach',
      'player-maximizer': 'Player Maximizer',
      'culture': 'Culture Builder'
    };
    
    // Get archetype display name
    let archetypeDisplay = archetypeMap[archetype] || archetype.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
    
    // Remove archetype prefix from sub_option (e.g., "builder-inspire" -> "inspire")
    let subOptionClean = subOption;
    if (subOption.startsWith(archetype + '-')) {
      subOptionClean = subOption.substring(archetype.length + 1);
    } else if (archetype === 'culture' && subOption.startsWith('builder-')) {
      subOptionClean = subOption.substring('builder-'.length);
    }
    
    // Format sub-option: capitalize words
    const formatSubOption = subOptionClean.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
    
    focusText = `${archetypeDisplay} (${formatSubOption})`;
  }
  
  document.getElementById('training-focus').textContent = focusText;
}

function renderPlayersTable() {
  if (!reportData || !reportData.players) return;
  
  const thead = document.getElementById('players-thead');
  const tbody = document.getElementById('players-tbody');
  
  // Clear existing content
  thead.innerHTML = '';
  tbody.innerHTML = '';
  
  // Build header
  const headerRow = document.createElement('tr');
  headerRow.appendChild(createHeaderCell('Name'));
  
  if (currentView === 'attributes') {
    // Attributes view: show all player attributes
    Object.keys(ATTRIBUTE_NAMES).forEach(attr => {
      headerRow.appendChild(createHeaderCell(attr));
    });
  } else {
    // Changes view: show only attributes that changed
    const changedAttrs = new Set();
    Object.values(reportData.player_changes || {}).forEach(changes => {
      Object.keys(changes).forEach(attr => changedAttrs.add(attr));
    });
    
    changedAttrs.forEach(attr => {
      headerRow.appendChild(createHeaderCell(attr));
    });
  }
  
  thead.appendChild(headerRow);
  
  // Build rows
  reportData.players.forEach(player => {
    const row = document.createElement('tr');
    row.appendChild(createCell(player.name));
    
    if (currentView === 'attributes') {
      // Show current attribute values
      Object.keys(ATTRIBUTE_NAMES).forEach(attr => {
        const value = player.attributes[attr] || 0;
        row.appendChild(createCell(value.toString()));
      });
    } else {
      // Show changes - get all changed attributes first
      const allChangedAttrs = new Set();
      Object.values(reportData.player_changes || {}).forEach(ch => {
        Object.keys(ch).forEach(attr => allChangedAttrs.add(attr));
      });
      
      // Show changes for this player (0 if no change)
      allChangedAttrs.forEach(attr => {
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        row.appendChild(createChangeCell(change));
      });
    }
    
    tbody.appendChild(row);
  });
}

function createHeaderCell(text) {
  const th = document.createElement('th');
  th.textContent = text;
  return th;
}

function createCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

function createChangeCell(change) {
  const td = document.createElement('td');
  
  if (change > 0) {
    td.textContent = `+${change}`;
    td.className = 'change-positive';
  } else if (change < 0) {
    td.textContent = change.toString();
    td.className = 'change-negative';
  } else {
    td.textContent = '0';
    td.className = 'change-zero';
  }
  
  return td;
}

function renderTeamAttributes() {
  if (!reportData) return;
  
  const grid = document.getElementById('team-attributes-grid');
  grid.innerHTML = '';
  
  const teamAttrs = reportData.team_attributes || {};
  const teamChanges = reportData.team_changes || {};
  
  // Define order of attributes
  const attrOrder = [
    'shot_threshold',
    'rebound_modifier',
    'offensive_efficiency',
    'defensive_efficiency',
    'fb_efficiency',
    'pt_efficiency',
    'foul_modifier',
    'turnover_modifier',
    'momentum_score',
    'team_chemistry',
    'fb_opp_modifier',
    'pt_opp_modifier'
  ];
  
  attrOrder.forEach(attrKey => {
    const item = createTeamAttrItem(attrKey, teamAttrs[attrKey], teamChanges[attrKey]);
    if (item) grid.appendChild(item);
  });
}

function createTeamAttrItem(attrKey, currentValue, change) {
  const displayName = TEAM_ATTR_NAMES[attrKey];
  if (!displayName) return null;
  
  // Handle undefined values
  if (currentValue === undefined || currentValue === null) {
    currentValue = 0;
  }
  if (change === undefined || change === null) {
    change = 0;
  }
  
  const item = document.createElement('div');
  item.className = 'team-attr-item';
  
  const label = document.createElement('div');
  label.className = 'attr-label';
  
  const nameSpan = document.createElement('span');
  nameSpan.textContent = displayName;
  
  const changeSpan = document.createElement('span');
  changeSpan.className = 'attr-change';
  
  if (change !== 0) {
    if (change > 0) {
      changeSpan.textContent = `+${change}`;
      changeSpan.className += ' change-positive';
    } else {
      changeSpan.textContent = change.toString();
      changeSpan.className += ' change-negative';
    }
  } else {
    changeSpan.textContent = 'No change';
    changeSpan.className += ' change-zero';
  }
  
  label.appendChild(nameSpan);
  label.appendChild(changeSpan);
  item.appendChild(label);
  
  // Special handling for different attribute types
  if (attrKey === 'team_chemistry') {
    // Progress bar (0-25)
    const barContainer = document.createElement('div');
    barContainer.className = 'chemistry-bar-container';
    
    const barFill = document.createElement('div');
    barFill.className = 'chemistry-bar-fill';
    const percentage = (currentValue / 25) * 100;
    barFill.style.width = `${percentage}%`;
    
    const barText = document.createElement('div');
    barText.className = 'chemistry-bar-text';
    barText.textContent = `${currentValue} / 25`;
    
    barContainer.appendChild(barFill);
    barContainer.appendChild(barText);
    item.appendChild(barContainer);
  } else if (attrKey === 'fb_opp_modifier' || attrKey === 'pt_opp_modifier') {
    // +/- Design - centered, bold, no value shown
    const indicatorContainer = document.createElement('div');
    indicatorContainer.className = 'plus-minus-container';
    indicatorContainer.style.textAlign = 'center';
    indicatorContainer.style.marginTop = 'var(--spacing-sm)';
    
    const indicator = document.createElement('span');
    indicator.className = 'plus-minus-indicator';
    indicator.style.fontWeight = '700';
    
    if (currentValue >= 10) {
      indicator.textContent = '+++';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue >= 5) {
      indicator.textContent = '++';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue >= 1) {
      indicator.textContent = '+';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue === 0) {
      indicator.textContent = '-';
      indicator.className += ' plus-minus-zero';
    } else if (currentValue >= -4) {
      indicator.textContent = '-';
      indicator.className += ' plus-minus-negative';
    } else if (currentValue >= -9) {
      indicator.textContent = '--';
      indicator.className += ' plus-minus-negative';
    } else {
      indicator.textContent = '---';
      indicator.className += ' plus-minus-negative';
    }
    
    indicatorContainer.appendChild(indicator);
    item.appendChild(indicatorContainer);
  } else {
    // Red/Green Pill Design
    const pill = createPill(currentValue, attrKey);
    item.appendChild(pill);
  }
  
  return item;
}

function createPill(originalValue, attrKey) {
  const pill = document.createElement('div');
  pill.className = 'attr-pill';
  
  // Center line
  const centerLine = document.createElement('div');
  centerLine.className = 'pill-center-line';
  pill.appendChild(centerLine);
  
  // Determine max value for this attribute (for proportional fill)
  let maxValue = 10; // Default for most attributes
  let displayValue = originalValue;
  let value = originalValue;
  
  if (attrKey === 'shot_threshold') {
    maxValue = 200;
  } else if (attrKey === 'rebound_modifier') {
    // Rebound modifier is 0.8-1.2, center at 1.0
    // We'll show deviation from 1.0
    maxValue = 0.2; // Max deviation is 0.2 (from 0.8 to 1.0 or 1.0 to 1.2)
    value = originalValue - 1.0; // Center at 0 for fill calculation
    displayValue = originalValue.toFixed(2); // Show original value with 2 decimals
  }
  
  // Value display - only show for Team Chemistry (handled separately)
  // For other pills, we don't show the value on top
  
  // Fill based on value
  if (value > 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-positive';
    const percentage = Math.min((value / maxValue) * 50, 50); // Max 50% to the right
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  } else if (value < 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-negative';
    const absValue = Math.abs(value);
    const percentage = Math.min((absValue / maxValue) * 50, 50); // Max 50% to the left
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  }
  
  return pill;
}

