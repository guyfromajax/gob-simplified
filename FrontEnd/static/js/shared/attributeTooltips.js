/**
 * Shared tooltip utility for attribute abbreviations
 * Provides full names for attributes and other abbreviations on hover
 * Uses custom CSS tooltips for better reliability than native title attribute
 */

const ATTRIBUTE_NAMES = {
  // Attributes
  SC: 'Scoring',
  SH: 'Shooting',
  ID: 'Inside Defense',
  OD: 'Outside Defense',
  PS: 'Passing',
  BH: 'Ball Handling',
  RB: 'Rebounding',
  ST: 'Strength',
  AG: 'Agility',
  FT: 'Free Throw',
  ND: 'Endurance',
  IQ: 'Basketball IQ',
  CH: 'Clutch',
  EM: 'Emotion',
  MO: 'Momentum',
  NG: 'Energy',
  
  // Other abbreviations
  POS: 'Position',
  HT: 'Height',
  WT: 'Weight',
  RT: 'Rating'
};

// Create a global tooltip element
let tooltipElement = null;

function createTooltipElement() {
  if (!tooltipElement) {
    tooltipElement = document.createElement('div');
    tooltipElement.id = 'attribute-tooltip-bubble';
    tooltipElement.style.cssText = `
      position: absolute;
      padding: 6px 10px;
      background: rgba(0, 0, 0, 0.95);
      color: #fff;
      font-size: 12px;
      white-space: nowrap;
      border-radius: 4px;
      pointer-events: none;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.2s, visibility 0.2s;
      z-index: 99999;
      font-family: 'Inter', sans-serif;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    `;
    document.body.appendChild(tooltipElement);
  }
  return tooltipElement;
}

// Inject tooltip CSS for cursor
function injectTooltipStyles() {
  if (!document.getElementById('attribute-tooltip-styles')) {
    const style = document.createElement('style');
    style.id = 'attribute-tooltip-styles';
    style.textContent = `
      .attr-tooltip {
        position: relative;
        cursor: help;
      }
    `;
    document.head.appendChild(style);
    console.log('[TOOLTIP] ✅ Injected tooltip CSS styles');
  }
}

// Show tooltip on hover
function setupTooltipEvents(element, tooltipText) {
  element.addEventListener('mouseenter', (e) => {
    const tooltip = createTooltipElement();
    tooltip.textContent = tooltipText;
    tooltip.style.opacity = '0';
    tooltip.style.visibility = 'visible';
    
    // Position tooltip above the element
    const rect = element.getBoundingClientRect();
    tooltip.style.left = `${rect.left + rect.width / 2}px`;
    tooltip.style.bottom = `${window.innerHeight - rect.top + 8}px`;
    tooltip.style.transform = 'translateX(-50%)';
    
    // Force reflow, then show
    tooltip.offsetHeight;
    tooltip.style.opacity = '1';
  });
  
  element.addEventListener('mouseleave', () => {
    if (tooltipElement) {
      tooltipElement.style.opacity = '0';
      tooltipElement.style.visibility = 'hidden';
    }
  });
  
  element.addEventListener('mousemove', (e) => {
    if (tooltipElement && tooltipElement.style.visibility === 'visible') {
      const rect = element.getBoundingClientRect();
      tooltipElement.style.left = `${rect.left + rect.width / 2}px`;
      tooltipElement.style.bottom = `${window.innerHeight - rect.top + 8}px`;
    }
  });
}

// Inject styles immediately when script loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectTooltipStyles);
} else {
  injectTooltipStyles();
}

/**
 * Initialize tooltips for attribute abbreviations
 * @param {HTMLElement} container - Container element to search for abbreviations
 * @param {Array<string>} selectors - CSS selectors for elements that need tooltips
 */
function initAttributeTooltips(container = document, selectors = []) {
  // Default selectors if none provided
  if (selectors.length === 0) {
    selectors = [
      'th',           // Table headers
      '.attr-label',  // Attribute labels in player cards
      '[data-attr]',  // Elements with data-attr attribute
      '.header-pos',  // Position headers
      '.slot-pos'     // Position in lineup slots
    ];
  }
  
  selectors.forEach(selector => {
    const elements = container.querySelectorAll(selector);
    let tooltipCount = 0;
    elements.forEach(element => {
      const text = element.textContent.trim();
      const upperText = text.toUpperCase();
      
      // Check if this is an attribute abbreviation
      if (ATTRIBUTE_NAMES[upperText]) {
        // Ensure styles are injected
        injectTooltipStyles();
        
        // Add class and setup event listeners
        element.classList.add('attr-tooltip');
        element.setAttribute('title', ATTRIBUTE_NAMES[upperText]); // Fallback
        setupTooltipEvents(element, ATTRIBUTE_NAMES[upperText]);
        tooltipCount++;
        console.log(`[TOOLTIP] ✅ Set tooltip for "${text}" → "${ATTRIBUTE_NAMES[upperText]}"`);
      }
      
      // Also check data-attr attribute if present
      if (element.hasAttribute('data-attr')) {
        const attr = element.getAttribute('data-attr').toUpperCase();
        if (ATTRIBUTE_NAMES[attr]) {
          element.classList.add('attr-tooltip');
          element.setAttribute('title', ATTRIBUTE_NAMES[attr]);
          setupTooltipEvents(element, ATTRIBUTE_NAMES[attr]);
          tooltipCount++;
          console.log(`[TOOLTIP] ✅ Set tooltip via data-attr for "${attr}" → "${ATTRIBUTE_NAMES[attr]}"`);
        }
      }
    });
    if (tooltipCount > 0) {
      console.log(`[TOOLTIP] Initialized ${tooltipCount} tooltips for selector "${selector}"`);
    }
  });
}

/**
 * Add tooltip to a specific element
 * @param {HTMLElement} element - Element to add tooltip to
 * @param {string} abbreviation - Abbreviation to look up
 */
function addTooltip(element, abbreviation) {
  const upperAbbr = abbreviation.toUpperCase();
  if (ATTRIBUTE_NAMES[upperAbbr]) {
    injectTooltipStyles();
    element.classList.add('attr-tooltip');
    element.setAttribute('title', ATTRIBUTE_NAMES[upperAbbr]);
    setupTooltipEvents(element, ATTRIBUTE_NAMES[upperAbbr]);
    console.log(`[TOOLTIP] addTooltip: "${abbreviation}" → "${ATTRIBUTE_NAMES[upperAbbr]}"`);
  } else {
    console.warn(`[TOOLTIP] No mapping found for abbreviation: "${abbreviation}"`);
  }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initAttributeTooltips, addTooltip, ATTRIBUTE_NAMES };
}

