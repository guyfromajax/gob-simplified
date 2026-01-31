/**
 * Analytics helper - pushes events to dataLayer for GTM/GA4.
 * Event names and parameters match the alpha launch plan spec.
 */
(function () {
  'use strict';

  function push(eventName, params) {
    if (typeof window.dataLayer === 'undefined') {
      window.dataLayer = [];
    }
    var payload = { event: eventName };
    if (params && typeof params === 'object') {
      Object.keys(params).forEach(function (key) {
        payload[key] = params[key];
      });
    }
    window.dataLayer.push(payload);
  }

  window.GOB_Analytics = {
    signup: function () {
      push('signup');
    },
    login: function () {
      push('login');
    },
    singleGameStarted: function () {
      push('single_game_started');
    },
    singleGameCompleted: function () {
      push('single_game_completed');
    },
    tournamentEntered: function () {
      push('tournament_entered');
    },
    tournamentGameStarted: function () {
      push('tournament_game_started');
    },
    tournamentGameCompleted: function () {
      push('tournament_game_completed');
    },
    franchiseEntered: function () {
      push('franchise_entered');
    },
    franchiseGameStarted: function () {
      push('franchise_game_started');
    },
    franchiseGameCompleted: function () {
      push('franchise_game_completed');
    },
    quarterAdvance: function (action) {
      push('quarter_advance', { action: action });
    }
  };
})();
