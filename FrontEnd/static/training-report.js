// Training Report Page JavaScript

function playSound(filename) {
  try {
    const base = (typeof window.API_CONFIG !== 'undefined' && window.API_CONFIG.buildStaticPath) ? window.API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(() => {});
  } catch (e) {}
}

const urlParams = new URLSearchParams(window.location.search);
const mode = urlParams.get('mode');
const franchiseId = urlParams.get('franchise_id');
const tournamentId = urlParams.get('tournament_id');
const teamId = urlParams.get('team_id');
const week = parseInt(urlParams.get('week'), 10);
const round = parseInt(urlParams.get('round'), 10); // For tournament mode (optional - backend will determine if not provided)

let reportData = null;
let currentView = 'changes'; // 'attributes' or 'changes'

// Attribute abbreviations mapping
// NOTE: Order is critical - this is the exact order attributes should be displayed horizontally
// MO (Momentum) is excluded from Training Report display
const ATTRIBUTE_ORDER = [
  'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'NG', 'EM'
];
const STATIC_COLUMNS = ['RT'];

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
  'NG': 'NG',
  'EM': 'EM',
  'MO': 'MO'
};

// Team attribute display names
const TEAM_ATTR_NAMES = {
  'shot_threshold': 'Shooting',
  'rebound_modifier': 'Rebounding',
  'offensive_efficiency': 'Offense',
  'defensive_efficiency': 'Defense',
  'fb_efficiency': 'Fast Breaks',
  'pt_efficiency': 'Press/Trap',
  'fight': 'Fight',
  'discipline': 'Discipline',
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
    'teamwork': 'Culture Builder - Team Building',
    'build-confidence': 'Culture Builder - Build Confidence'
  }
};

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
  // SS&S: For tournament mode, round is optional (backend will determine from state)
  // For franchise mode, week is required
  if (!mode || !teamId) {
    console.error('Missing required URL parameters: mode and team_id are required');
    return;
  }
  
  if (mode === 'franchise' && !week) {
    console.error('Missing required URL parameter: week is required for franchise mode');
    return;
  }
  
  // Tournament mode: round is optional - backend will determine from training_status

  // Set up view toggle
  setupViewToggle();
  
  // Set up locker room button
  setupLockerRoomButton();
  
  // Load training report data
  loadTrainingReport();
});

function setupViewToggle() {
  const toggleButtons = document.querySelectorAll('.toggle-btn');
  // Enforce initial active button from currentView
  toggleButtons.forEach(b => {
    if (b.dataset.view === currentView) b.classList.add('active');
    else b.classList.remove('active');
  });
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      playSound('click-tiny.wav');
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
    playSound('click-strong.wav');
    if (mode === 'franchise') {
      const lockerRoomUrl = (typeof resolveFranchiseLockerRoomUrl === 'function')
        ? resolveFranchiseLockerRoomUrl({
            franchiseId: franchiseId,
            teamId: teamId
          })
        : `/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`;
      window.location.href = lockerRoomUrl;
    } else if (mode === 'tournament') {
      // Use same pattern as franchise mode - tournament.html is the command center
      window.location.href = `/tournament.html?tournament_id=${tournamentId}&team_id=${teamId}`;
    }
  });
}

async function loadTrainingReport() {
  try {
    const params = new URLSearchParams({
      mode: mode,
      team_id: teamId
    });
    
    if (franchiseId) {
      params.set('franchise_id', franchiseId);
      params.set('week', week);
    }
    if (tournamentId) {
      params.set('tournament_id', tournamentId);
      // SS&S: Only send round/week if provided - backend will determine from state if not provided
      if (round) {
        params.set('round', round);
      } else if (week) {
        params.set('week', week); // Backward compatibility
      }
      // If neither round nor week provided, backend will determine from training_status
    }
    
    console.log('🔍 [TRAINING REPORT] Loading with params:', Object.fromEntries(params.entries()));
    
    const response = await fetch(`${API_CONFIG.buildUrl('/franchise/training-report')}?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to load training report: ${response.statusText}`);
    }
    
    reportData = await response.json();
    console.log('🔍 [TRAINING REPORT] Loaded data:', reportData);
    console.log('🔍 [TRAINING REPORT] Players count:', reportData.players?.length || 0);
    console.log('🔍 [TRAINING REPORT] Player changes:', reportData.player_changes);
    console.log('🔍 [TRAINING REPORT] Has plays_data:', !!reportData.plays_data, 'Keys:', reportData.plays_data ? Object.keys(reportData.plays_data) : 'none');
    console.log('🔍 [TRAINING REPORT] Has scouting_data:', !!reportData.scouting_data, 'Keys:', reportData.scouting_data ? Object.keys(reportData.scouting_data) : 'none');
    console.log('🔍 [TRAINING REPORT] Has plays_effectiveness_changes:', !!reportData.plays_effectiveness_changes, reportData.plays_effectiveness_changes);
    console.log('🔍 [TRAINING REPORT] Has defenses_effectiveness_changes:', !!reportData.defenses_effectiveness_changes, reportData.defenses_effectiveness_changes);
    
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
  
  // Render playbook summary
  renderPlaybookSummary();
  
  // Render training notes
  renderTrainingNotes();
}

function renderHeader() {
  // For tournament mode, display "Round X"; for franchise mode, display "Week X"
  const periodLabel = mode === 'tournament' ? 'Round' : 'Week';
  const periodValue = mode === 'tournament' ? (reportData.round || round) : reportData.week;
  document.getElementById('week-number').textContent = periodValue || '--';
  
  // Update label
  const weekLabel = document.getElementById('week-label');
  if (weekLabel) {
    weekLabel.textContent = periodLabel + ':';
  }
  
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
      'culture': 'Culture Builder',
      'culture-builder': 'Culture Builder'
    };
    
    // Get archetype display name
    let archetypeDisplay = archetypeMap[archetype] || archetype.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');

    // Backend may send explicit leaf label (e.g. Team Building vs Teamwork—which share no API token ambiguity once labeled)
    const leafFromApi = focus.leaf_display_name;
    if (leafFromApi) {
      focusText = `${leafFromApi} (${archetypeDisplay})`;
    } else {
    // Remove archetype prefix from sub_option (e.g., "systems-coach-offense" -> "offense")
    let subOptionClean = subOption;
    if (subOption.startsWith(archetype + '-')) {
      subOptionClean = subOption.substring(archetype.length + 1);
    } else if (archetype === 'culture' && subOption.startsWith('builder-')) {
      subOptionClean = subOption.substring('builder-'.length);
    }
    
    // Special handling for systems-coach: remove "coach-" prefix if present
    if (archetype === 'systems-coach' && subOptionClean.startsWith('coach-')) {
      subOptionClean = subOptionClean.substring('coach-'.length);
    }
    
    // Format sub-option: capitalize words
    const formatSubOption = subOptionClean.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
    
    // Format: focus (archetype) - focus outside, archetype inside parentheses
    focusText = `${formatSubOption} (${archetypeDisplay})`;
    }
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
  
  let attributeList = [];
  if (currentView === 'attributes') {
    // Attributes view: show all player attributes in exact order
    attributeList = ATTRIBUTE_ORDER.filter(attr => ATTRIBUTE_NAMES[attr]);
    attributeList.forEach(attr => {
      headerRow.appendChild(createHeaderCell(attr));
    });
  } else {
    // Changes view: show only attributes that changed, but maintain order
    const changedAttrs = new Set();
    Object.values(reportData.player_changes || {}).forEach(changes => {
      Object.keys(changes).forEach(attr => changedAttrs.add(attr));
    });
    
    // Filter to only changed attrs, but maintain ATTRIBUTE_ORDER
    attributeList = ATTRIBUTE_ORDER.filter(attr => changedAttrs.has(attr));
    attributeList.forEach(attr => {
      headerRow.appendChild(createHeaderCell(attr));
    });
  }

  STATIC_COLUMNS.forEach(col => {
    headerRow.appendChild(createHeaderCell(col));
  });
  
  thead.appendChild(headerRow);
  
  // Build rows
  getSortedPlayersForReport().forEach(player => {
    const row = document.createElement('tr');
    row.appendChild(createCell(player.name));
    
    if (currentView === 'attributes') {
      // Show current attribute values with tooltips
      attributeList.forEach(attr => {
        const value = player.attributes[attr] || (attr === 'NG' ? 1.0 : attr === 'EM' ? 50 : attr === 'MO' ? 0 : 0);
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        row.appendChild(createAttributeCell(attr, value, change));
      });
    } else {
      // Show changes for this player (0 if no change)
      attributeList.forEach(attr => {
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        row.appendChild(createChangeCell(change));
      });
    }

    row.appendChild(createCell(getPlayerHighestRt(player)));
    
    tbody.appendChild(row);
  });
  
  // Add aggregated row for Training Changes view
  if (currentView === 'changes' && attributeList.length > 0) {
    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row';
    totalRow.appendChild(createCell('Total'));
    
    // Calculate totals for each attribute
    attributeList.forEach(attr => {
      let total = 0;
      reportData.players.forEach(player => {
        const changes = reportData.player_changes[player.name] || {};
        total += changes[attr] || 0;
      });
      totalRow.appendChild(createChangeCell(total));
    });
    
    tbody.appendChild(totalRow);
  }
}

function getPlayerHighestRt(player) {
  const ratings = player && player.position_ratings ? player.position_ratings : {};
  const values = Object.values(ratings).map(v => Number(v) || 0);
  if (!values.length) return 0;
  return Math.max(...values);
}

function getSortedPlayersForReport() {
  return (reportData.players || [])
    .map((player, index) => ({ player, index }))
    .sort((a, b) => {
      const rtDiff = getPlayerHighestRt(b.player) - getPlayerHighestRt(a.player);
      if (rtDiff !== 0) return rtDiff;
      return a.index - b.index;
    })
    .map(entry => entry.player);
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

function createAttributeCell(attr, value, change) {
  const td = document.createElement('td');
  td.className = 'attribute-value-cell';
  
  // Special handling for NG, EM, MO
  if (attr === 'NG') {
    // Display with 2 decimal places
    td.textContent = typeof value === 'number' ? value.toFixed(2) : '1.00';
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  } else if (attr === 'EM') {
    // Display with emoji
    const emoji = getEmotionEmoji(value);
    td.innerHTML = emoji;
    td.style.fontSize = '1.5rem';
    td.style.textAlign = 'center';
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  } else if (attr === 'MO') {
    // Display with red/green pill (no integer on top)
    const pillContainer = createMomentumPill(value);
    td.appendChild(pillContainer);
    td.style.padding = 'var(--spacing-xs)';
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  } else {
    // Standard integer display with tooltip - show full value (no rounding)
    // Ensure we display the full integer value, not a rounded version
    const displayValue = typeof value === 'number' ? Math.floor(value) : (typeof value === 'string' ? parseInt(value, 10) || 0 : 0);
    td.textContent = displayValue.toString();
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  }
  
  return td;
}

function getEmotionEmoji(em) {
  const emValue = typeof em === 'number' ? em : 50;
  if (emValue >= 80) return '😎';        // Sunglasses
  else if (emValue >= 60) return '😊';   // Big smile
  else if (emValue >= 40) return '😐';   // Straight face
  else if (emValue >= 20) return '😕';   // Slight frown
  else return '😞';                      // Sad face
}

function createMomentumPill(mo) {
  const container = document.createElement('div');
  container.className = 'momentum-pill-container';
  container.style.position = 'relative';
  container.style.width = '100%';
  container.style.height = '30px';
  container.style.background = 'rgba(0, 0, 0, 0.3)';
  container.style.borderRadius = '15px';
  container.style.overflow = 'hidden';
  
  // Center line
  const centerLine = document.createElement('div');
  centerLine.style.position = 'absolute';
  centerLine.style.left = '50%';
  centerLine.style.top = '0';
  centerLine.style.bottom = '0';
  centerLine.style.width = '2px';
  centerLine.style.background = 'var(--color-warning)';
  centerLine.style.transform = 'translateX(-50%)';
  centerLine.style.zIndex = '2';
  container.appendChild(centerLine);
  
  const moValue = typeof mo === 'number' ? mo : 0;
  const maxValue = 10; // MO ranges from -10 to +10
  
  // Fill based on value
  if (moValue > 0) {
    const fill = document.createElement('div');
    fill.style.position = 'absolute';
    fill.style.left = '50%';
    fill.style.top = '0';
    fill.style.bottom = '0';
    fill.style.background = 'var(--color-success)';
    fill.style.transition = 'width 0.3s ease';
    fill.style.zIndex = '1';
    const percentage = Math.min((moValue / maxValue) * 50, 50); // Max 50% to the right
    fill.style.width = `${percentage}%`;
    container.appendChild(fill);
  } else if (moValue < 0) {
    const fill = document.createElement('div');
    fill.style.position = 'absolute';
    fill.style.right = '50%';
    fill.style.top = '0';
    fill.style.bottom = '0';
    fill.style.background = 'var(--color-error)';
    fill.style.transition = 'width 0.3s ease';
    fill.style.zIndex = '1';
    const absValue = Math.abs(moValue);
    const percentage = Math.min((absValue / maxValue) * 50, 50); // Max 50% to the left
    fill.style.width = `${percentage}%`;
    container.appendChild(fill);
  }
  
  return container;
}

function formatChangeForTooltip(change, attrKey = null) {
  // ✅ FIX: Format rebound_modifier changes to 2 decimal places
  const formattedChange = attrKey === 'rebound_modifier' 
    ? (change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2))
    : (change > 0 ? `+${change}` : change.toString());
  
  if (change > 0) {
    return formattedChange;
  } else if (change < 0) {
    return formattedChange;
  } else {
    return '0';
  }
}

function showAttributeTooltip(event) {
  const cell = event.target;
  const changeText = cell.getAttribute('data-tooltip');
  if (!changeText) return;
  
  // Create tooltip element if it doesn't exist
  let tooltip = document.getElementById('attribute-tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'attribute-tooltip';
    tooltip.className = 'attribute-tooltip';
    document.body.appendChild(tooltip);
  }
  
  // Determine color based on change value
  const change = parseInt(changeText.replace('+', ''), 10);
  if (change > 0) {
    tooltip.className = 'attribute-tooltip attribute-tooltip-positive';
  } else if (change < 0) {
    tooltip.className = 'attribute-tooltip attribute-tooltip-negative';
  } else {
    tooltip.className = 'attribute-tooltip attribute-tooltip-zero';
  }
  
  tooltip.textContent = changeText;
  tooltip.style.display = 'block';
  positionAttributeTooltip(event);
}

function hideAttributeTooltip() {
  const tooltip = document.getElementById('attribute-tooltip');
  if (tooltip) {
    tooltip.style.display = 'none';
  }
}

function positionAttributeTooltip(event) {
  const tooltip = document.getElementById('attribute-tooltip');
  if (!tooltip || tooltip.style.display === 'none') return;
  
  const cell = event.target;
  const rect = cell.getBoundingClientRect();
  
  // Position tooltip above the cell
  tooltip.style.left = `${rect.left + rect.width / 2}px`;
  tooltip.style.top = `${rect.top - 10}px`;
  tooltip.style.transform = 'translate(-50%, -100%)';
}

function createChangeCell(change) {
  const td = document.createElement('td');
  
  if (change > 0) {
    td.textContent = `+${change}`;
    td.className = change > 5 ? 'change-gold' : 'change-positive';
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
    'fight',
    'discipline',
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
    // Special handling for shot_threshold: negative change (decrease) is good, positive change (increase) is bad
    if (attrKey === 'shot_threshold') {
      // Invert: negative change (good) shows as green with +, positive change (bad) shows as red with -
      const absChange = Math.abs(change);
      if (change < 0) {
        // Decrease is good - show as green with +
        changeSpan.textContent = `+${absChange}`;
        changeSpan.className += absChange > 5 ? ' change-gold' : ' change-positive';
      } else {
        // Increase is bad - show as red with -
        changeSpan.textContent = `-${absChange}`;
        changeSpan.className += ' change-negative';
      }
    } else if (attrKey === 'rebound_modifier') {
      // Format rebound_modifier changes to 2 decimal places
      const formattedChange = change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
      changeSpan.textContent = formattedChange;
      if (change > 0) {
        changeSpan.className += change > 5 ? ' change-gold' : ' change-positive';
      } else {
        changeSpan.className += ' change-negative';
      }
    } else {
      // Standard handling for other attributes
      const formattedChange = change > 0 ? `+${change}` : change.toString();
      changeSpan.textContent = formattedChange;
      if (change > 0) {
        changeSpan.className += change > 5 ? ' change-gold' : ' change-positive';
      } else {
        changeSpan.className += ' change-negative';
      }
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
    maxValue = 100; // Range is 10 to 210, center at 110, so max deviation is 100
    value = 110 - originalValue; // Invert: lower is better (positive/green), higher is worse (negative/red)
  } else if (attrKey === 'rebound_modifier') {
    // Rebound modifier is 0.0-0.4, center at 0.2
    // We'll show deviation from 0.2
    maxValue = 0.2; // Max deviation is 0.2 (from 0.0 to 0.2 or 0.2 to 0.4)
    value = originalValue - 0.2; // Center at 0 for fill calculation
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

function renderPlaybookSummary() {
  if (!reportData) return;
  
  const container = document.getElementById('playbook-summary-container');
  container.innerHTML = '';
  
  const plays_data = reportData.plays_data || {};
  const scouting_data = reportData.scouting_data || {};
  const plays_changes = reportData.plays_effectiveness_changes || {};
  const defenses_changes = reportData.defenses_effectiveness_changes || {};
  
  console.log('📚 [PLAYBOOK SUMMARY] Rendering playbook summary');
  console.log('📚 [PLAYBOOK SUMMARY] plays_data:', plays_data);
  console.log('📚 [PLAYBOOK SUMMARY] scouting_data:', scouting_data);
  console.log('📚 [PLAYBOOK SUMMARY] plays_changes:', plays_changes);
  console.log('📚 [PLAYBOOK SUMMARY] defenses_changes:', defenses_changes);
  
  // Debug logging
  console.log('📊 [PLAYBOOK SUMMARY] reportData keys:', Object.keys(reportData));
  console.log('📊 [PLAYBOOK SUMMARY] plays_data:', plays_data);
  console.log('📊 [PLAYBOOK SUMMARY] scouting_data:', scouting_data);
  console.log('📊 [PLAYBOOK SUMMARY] plays_changes:', plays_changes);
  console.log('📊 [PLAYBOOK SUMMARY] defenses_changes:', defenses_changes);
  console.log('📊 [PLAYBOOK SUMMARY] Number of plays:', Object.keys(plays_data).length);
  
  // Organize plays by type
  const motion_plays = [];
  const set_plays = [];
  
  for (const [play_name, play_data] of Object.entries(plays_data)) {
    if (typeof play_data === 'object' && play_data !== null) {
      const play_type = play_data.play_type || '';
      if (play_type === 'motion') {
        motion_plays.push({ name: play_name, ...play_data });
      } else if (play_type === 'set_play') {
        set_plays.push({ name: play_name, ...play_data });
      }
    }
  }
  
  // Sort plays by name
  motion_plays.sort((a, b) => a.name.localeCompare(b.name));
  set_plays.sort((a, b) => a.name.localeCompare(b.name));
  
  // Organize defenses
  const man_defenses = [];
  const zone_defenses = [];
  
  if (scouting_data.defense) {
    for (const [defense_name, defense_data] of Object.entries(scouting_data.defense)) {
      if (typeof defense_data === 'object' && defense_data !== null) {
        if (defense_name === 'Man') {
          man_defenses.push({ name: defense_name, ...defense_data });
        } else if (defense_name.includes('Zone')) {
          zone_defenses.push({ name: defense_name, ...defense_data });
        }
      }
    }
  }
  
  // Sort defenses by name
  man_defenses.sort((a, b) => a.name.localeCompare(b.name));
  zone_defenses.sort((a, b) => a.name.localeCompare(b.name));
  
  // Render Offense section
  const offenseSection = document.createElement('div');
  offenseSection.className = 'playbook-category';
  
  const offenseTitle = document.createElement('h3');
  offenseTitle.textContent = 'Offense';
  offenseSection.appendChild(offenseTitle);
  
  // Motion Plays
  if (motion_plays.length > 0) {
    motion_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking
      const playRow = createPlayRow(play.name, play, plays_changes[play.name] || 0);
      offenseSection.appendChild(playRow);
    });
  }
  
  // Set Plays
  if (set_plays.length > 0) {
    set_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking
      const playRow = createPlayRow(play.name, play, plays_changes[play.name] || 0);
      offenseSection.appendChild(playRow);
    });
  }
  
  // Empty row
  const emptyRow = document.createElement('div');
  emptyRow.className = 'playbook-empty-row';
  offenseSection.appendChild(emptyRow);
  
  container.appendChild(offenseSection);
  
  // Render Defense section
  const defenseSection = document.createElement('div');
  defenseSection.className = 'playbook-category';
  
  const defenseTitle = document.createElement('h3');
  defenseTitle.textContent = 'Defense';
  defenseSection.appendChild(defenseTitle);
  
  // Man Defenses
  if (man_defenses.length > 0) {
    man_defenses.forEach(defense => {
      // Pass full defense object to access effectiveness, momentum, cloaking
      const defenseRow = createPlayRow(defense.name, defense, defenses_changes[defense.name] || 0);
      defenseSection.appendChild(defenseRow);
    });
  }
  
  // Zone Defenses
  if (zone_defenses.length > 0) {
    zone_defenses.forEach(defense => {
      // Pass full defense object to access effectiveness, momentum, cloaking
      const defenseRow = createPlayRow(defense.name, defense, defenses_changes[defense.name] || 0);
      defenseSection.appendChild(defenseRow);
    });
  }
  
  container.appendChild(defenseSection);
}

function createPlayRow(playName, playData, change) {
  // playData can be an object with effectiveness, momentum, cloaking, or just a number (effectiveness)
  // Handle both formats for backward compatibility
  const effectiveness = typeof playData === 'object' ? (playData.effectiveness || 0) : (playData || 0);
  const momentum = typeof playData === 'object' ? (playData.momentum || 0) : 0;
  const cloaking = typeof playData === 'object' ? (playData.cloaking || 0) : 0;
  
  const row = document.createElement('div');
  row.className = 'playbook-row';
  
  // Play name
  const nameDiv = document.createElement('div');
  nameDiv.className = 'playbook-name';
  nameDiv.textContent = playName;
  row.appendChild(nameDiv);
  
  // Metrics container - holds all three bars
  const metricsContainer = document.createElement('div');
  metricsContainer.className = 'playbook-metrics-container';
  
  // Command (Effectiveness) - Blue, 0-100 scale
  const commandMetric = createMetricBar('Command', effectiveness, 100, '#4a90e2', change);
  metricsContainer.appendChild(commandMetric);
  
  // Momentum - Orange, 0-10 scale
  const momentumMetric = createMetricBar('Momentum', momentum, 10, '#ff9800', null);
  metricsContainer.appendChild(momentumMetric);
  
  // Cloaking - Purple, 0-10 scale
  const cloakingMetric = createMetricBar('Cloaking', cloaking, 10, '#9c27b0', null);
  metricsContainer.appendChild(cloakingMetric);
  
  row.appendChild(metricsContainer);
  
  return row;
}

function createMetricBar(title, value, maxValue, color, change) {
  const metricDiv = document.createElement('div');
  metricDiv.className = 'playbook-metric';
  
  // Title
  const titleDiv = document.createElement('div');
  titleDiv.className = 'playbook-metric-title';
  titleDiv.textContent = title;
  metricDiv.appendChild(titleDiv);
  
  // Progress bar container
  const progressContainer = document.createElement('div');
  progressContainer.className = 'playbook-progress-container';
  
  const progressBar = document.createElement('div');
  progressBar.className = 'playbook-progress-bar';
  
  const progressFill = document.createElement('div');
  progressFill.className = 'playbook-progress-fill';
  progressFill.style.backgroundColor = color;
  const percentage = Math.min(100, (value / maxValue) * 100);
  progressFill.style.width = `${percentage}%`;
  
  progressBar.appendChild(progressFill);
  progressContainer.appendChild(progressBar);
  metricDiv.appendChild(progressContainer);
  
  // Change indicator (only for Command/Effectiveness)
  if (change !== null && change !== undefined) {
    const changeDiv = document.createElement('div');
    changeDiv.className = 'playbook-change';
    
    if (change > 0) {
      changeDiv.textContent = `+${change}`;
      changeDiv.style.color = '#4CAF50'; // Green
    } else if (change < 0) {
      changeDiv.textContent = `-${Math.abs(change)}`;
      changeDiv.style.color = '#f44336'; // Red
    } else {
      changeDiv.textContent = '0';
      changeDiv.style.color = '#ffffff'; // White
    }
    
    metricDiv.appendChild(changeDiv);
  }
  
  return metricDiv;
}

function renderTrainingNotes() {
  if (!reportData) return;
  
  const container = document.getElementById('training-notes-container');
  container.innerHTML = '';
  
  const training_notes = reportData.training_notes || [];
  
  if (training_notes.length === 0) {
    // Show placeholder if no notes
    const placeholder = document.createElement('p');
    placeholder.className = 'notes-placeholder';
    placeholder.textContent = 'No training notes for this session.';
    placeholder.style.color = '#999';
    placeholder.style.fontStyle = 'italic';
    container.appendChild(placeholder);
    return;
  }
  
  // Render each note as a paragraph
  training_notes.forEach(note => {
    const noteElement = document.createElement('p');
    noteElement.className = 'training-note';
    noteElement.textContent = note;
    container.appendChild(noteElement);
  });
}
