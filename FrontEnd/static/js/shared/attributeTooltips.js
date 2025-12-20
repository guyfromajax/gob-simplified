/**
 * Shared tooltip utility for attribute abbreviations
 * Provides full names for attributes and other abbreviations on hover
 */

const ATTRIBUTE_NAMES = {
  // Attributes
  SC: 'Scoring',
  SH: 'Shooting',
  ID: 'Interior Defense',
  OD: 'Outside Defense',
  PS: 'Passing',
  BH: 'Ball Handling',
  RB: 'Rebounding',
  ST: 'Strength',
  AG: 'Agility',
  FT: 'Free Throw',
  ND: 'No Dumb Fouls',
  IQ: 'Basketball IQ',
  CH: 'Clutch',
  EM: 'Energy/Momentum',
  MO: 'Moxie',
  NG: 'Energy',
  
  // Other abbreviations
  POS: 'Position',
  HT: 'Height',
  WT: 'Weight',
  RT: 'Rating'
};

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
    elements.forEach(element => {
      const text = element.textContent.trim();
      const upperText = text.toUpperCase();
      
      // Check if this is an attribute abbreviation
      if (ATTRIBUTE_NAMES[upperText]) {
        element.setAttribute('title', ATTRIBUTE_NAMES[upperText]);
        element.style.cursor = 'help';
      }
      
      // Also check data-attr attribute if present
      if (element.hasAttribute('data-attr')) {
        const attr = element.getAttribute('data-attr').toUpperCase();
        if (ATTRIBUTE_NAMES[attr]) {
          element.setAttribute('title', ATTRIBUTE_NAMES[attr]);
          element.style.cursor = 'help';
        }
      }
    });
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
    element.setAttribute('title', ATTRIBUTE_NAMES[upperAbbr]);
    element.style.cursor = 'help';
  }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initAttributeTooltips, addTooltip, ATTRIBUTE_NAMES };
}

