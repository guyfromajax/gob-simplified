/* GOB Team Builder — the league, grounded in the shipped data model.

   Read from develop:
   - js/shared/teamPicker.js — CONFERENCE_GEOGRAPHY (conference-level), band
     cutoffs 26/25/26/25/26, region letter = floor((n-1)/2)
   - common.js — nameToTeamSlug + TEAM_ASSET_SPEC; card art is
     /images/teams/<slug>/<slug>_banner_card.webp, fallback general
   - images/teams/ — the canonical 128 program folders

   The 128 slugs below ARE the league. Display names are title-cased from the
   slug with exceptions where the slug rule is lossy (apostrophes/periods
   stripped, hyphens → spaces); in production they come from /teams.
   Conference assignment, tier values and records are fixture data. */
(function () {
  'use strict';

  var TIERS = {
    talent:     ['Loaded', 'Deep', 'Average', 'Thin', 'Rebuilding'],
    prestige:   ['Blue Blood', 'Established', 'Respected', 'Climbing', 'Unproven'],
    size:       ['Tallest', 'Taller', 'Balanced', 'Quicker', 'Quickest'],
    experience: ['Most Experienced', 'Experienced', 'Balanced', 'Young', 'Youngest']
  };

  /* verbatim from teamPicker.js */
  var CONFERENCE_GEOGRAPHY = {
    1: ['Pennsylvania', 'New Jersey', 'Delaware'],
    2: ['West Virginia', 'North Carolina', 'Virginia', 'Maryland'],
    3: ['Massachusetts', 'Rhode Island', 'Vermont', 'Maine', 'New Hampshire', 'Connecticut'],
    4: ['New York', 'East Canada', 'Europe'],
    5: ['Michigan', 'Ohio', 'Indiana'],
    6: ['Illinois', 'Minnesota', 'Wisconsin'],
    7: ['Mississippi', 'Tennessee', 'Kentucky', 'South Carolina', 'Alabama'],
    8: ['Florida', 'Georgia'],
    9: ['Iowa', 'Kansas', 'Missouri'],
    10: ['Nebraska', 'South Dakota', 'North Dakota', 'Wyoming', 'Montana', 'Central Canada'],
    11: ['Oklahoma', 'Texas', 'Arkansas'],
    12: ['Texas', 'Louisiana'],
    13: ['Arizona', 'New Mexico', 'Nevada', 'Colorado', 'Utah'],
    14: ['Idaho', 'Washington', 'Oregon', 'West Canada'],
    15: ['California'],
    16: ['California', 'Hawaii', 'Alaska', 'Asia', 'Australia']
  };

  /* PROPOSED — the numbers, regions and geography are the real ones */
  var CONF_NAMES = {
    1: 'Keystone', 2: 'Tidewater', 3: 'Northern Reach', 4: 'Metro East',
    5: 'Iron Belt', 6: 'Lakeland', 7: 'Delta', 8: 'Gulf Shore',
    9: 'Heartland', 10: 'Frontier', 11: 'Red River', 12: 'Bayou',
    13: 'High Desert', 14: 'Ridgeline', 15: 'Golden Coast', 16: 'Pacific Rim'
  };

  /* [slug, display name] — the canonical 128 from images/teams/.
     Names are title-cased from the slug because nameToTeamSlug is lossy for
     internal capitals, periods and apostrophes. In production they must come
     from /teams; do not derive them there. */
  var LEAGUE = [
    ['abilene', "Abilene"],
    ['ada', "Ada"],
    ['amariabi_international', "Amariabi International"],
    ['amarillo_tech', "Amarillo Tech"],
    ['ann_arbor', "Ann Arbor"],
    ['appalachia', "Appalachia"],
    ['archbishop_mcclellan', "Archbishop McClellan"],
    ['austin', "Austin"],
    ['austin_west', "Austin West"],
    ['barton_lutheran', "Barton Lutheran"],
    ['bayou_district', "Bayou District"],
    ['bentley_truman', "Bentley-Truman"],
    ['berkley', "Berkley"],
    ['biloxi', "Biloxi"],
    ['boise', "Boise"],
    ['border_academy', "Border Academy"],
    ['burroughs', "Burroughs"],
    ['cagers_world', "Cagers World"],
    ['cardinal_conor', "Cardinal Conor"],
    ['casino_row', "Casino Row"],
    ['chambless_global', "Chambless Global"],
    ['chapel_hill', "Chapel Hill"],
    ['circus_circus', "Circus Circus"],
    ['cleveland_carlysle', "Cleveland-Carlysle"],
    ['columbus', "Columbus"],
    ['concord', "Concord"],
    ['couer_dalene', "Couer d'Alene"],
    ['crickstown', "Crickstown"],
    ['crimson_county', "Crimson County"],
    ['crofton', "Crofton"],
    ['cupertino', "Cupertino"],
    ['d1_institute', "D1 Institute"],
    ['dade_academy', "Dade Academy"],
    ['decatur_dei', "DeCatur Dei"],
    ['deland', "Deland"],
    ['desert_regional', "Desert Regional"],
    ['dillinger', "Dillinger"],
    ['durham', "Durham"],
    ['east_rockies', "East Rockies"],
    ['empire_city', "Empire City"],
    ['evanston', "Evanston"],
    ['falls_academy', "Falls Academy"],
    ['fielding', "Fielding"],
    ['four_corners', "Four Corners"],
    ['gainesville', "Gainesville"],
    ['garden_elites', "Garden Elites"],
    ['gp_prep_school', "GP Prep School"],
    ['grayson_ranch', "Grayson Ranch"],
    ['grizzly_academy', "Grizzly Academy"],
    ['grupenberg', "Grupenberg"],
    ['ha_rushmore', "HA Rushmore"],
    ['hana_road', "Hana Road"],
    ['harding_central', "Harding Central"],
    ['hardwood_fields', "Hardwood Fields"],
    ['hollywood_prep', "Hollywood Prep"],
    ['houston_jesuit', "Houston Jesuit"],
    ['huntington_canyon', "Huntington Canyon"],
    ['hyde_methodist', "Hyde Methodist"],
    ['ida', "IDA"],
    ['independence', "Independence"],
    ['iowa_academy', "Iowa Academy"],
    ['ivy_prep', "Ivy Prep"],
    ['juneau_nome', "Juneau Nome"],
    ['kenton', "Kenton"],
    ['keys_high', "Keys High"],
    ['knoxville', "Knoxville"],
    ['lancaster', "Lancaster"],
    ['lawrence', "Lawrence"],
    ['lewis_catholic', "Lewis Catholic"],
    ['lexington', "Lexington"],
    ['little_york', "Little York"],
    ['long_island_methodist', "Long Island Methodist"],
    ['mahala_alou', "Mahala Alou"],
    ['melbourne_americas', "Melbourne Americas"],
    ['middletex', "Middletex"],
    ['minot', "Minot"],
    ['mobile', "Mobile"],
    ['monroe_hayes', "Monroe-Hayes"],
    ['montpeiler', "Montpeiler"],
    ['morristown', "Morristown"],
    ['mt_simmons', "Mt. Simmons"],
    ['mynsk', "Mynsk"],
    ['myrtle_private', "Myrtle Private"],
    ['nickel_beach', "Nickel Beach"],
    ['norman', "Norman"],
    ['north_columbus', "North Columbus"],
    ['ocean_city', "Ocean City"],
    ['ozark_centre', "Ozark Centre"],
    ['pacific_all_stars', "Pacific All Stars"],
    ['pan_handle_limited', "Pan Handle Limited"],
    ['pikes_prep', "Pike's Prep"],
    ['providence', "Providence"],
    ['queens_guard', "Queen's Guard"],
    ['quigley_catholic', "Quigley Catholic"],
    ['rainier_central', "Rainier Central"],
    ['rancho_estrada', "Rancho Estrada"],
    ['reardon_mayes', "Reardon-Mayes"],
    ['redwood_high', "Redwood High"],
    ['reyes_santiago', "Reyes Santiago"],
    ['rivers_edge', "River's Edge"],
    ['rodeo_circuit', "Rodeo Circuit"],
    ['sacred_heart', "Sacred Heart"],
    ['salem', "Salem"],
    ['san_jose', "San Jose"],
    ['seattle_aaa', "Seattle AAA"],
    ['south_lancaster', "South Lancaster"],
    ['southwest_miner', "Southwest Miner"],
    ['st_peters', "St. Peters"],
    ['stormwood', "Stormwood"],
    ['swoosh', "Swoosh"],
    ['syracuse', "Syracuse"],
    ['tallahassee', "Tallahassee"],
    ['templeton_wesley', "Templeton-Wesley"],
    ['toronto_limited', "Toronto Limited"],
    ['tower_academy', "Tower Academy"],
    ['tri_cities_prep', "Tri-Cities Prep"],
    ['tucson', "Tucson"],
    ['two_rivers', "Two Rivers"],
    ['upper_peninsula', "Upper Peninsula"],
    ['upstate', "Upstate"],
    ['valdosta_valley', "Valdosta Valley"],
    ['valley_high', "Valley High"],
    ['vancouver', "Vancouver"],
    ['wacker_west', "Wacker West"],
    ['wash_u_prep', "Wash U Prep"],
    ['washington_carver', "Washington Carver"],
    ['west_ocean_city', "West Ocean City"],
    ['xavien', "Xavien"]
  ];

  /* Conference membership. Assigned from the program's own place name onto the
     real CONFERENCE_GEOGRAPHY so the header and its contents agree — Boise and
     Seattle AAA sit in Conference 14 (Idaho · Washington · Oregon · West
     Canada), Tucson in 13, Tallahassee in 8. Programs whose names carry no
     geography fill the remaining slots to keep every conference at eight.
     In production this is `team.conference` from /teams. */
  var CONF_BY_SLUG = {
      "lancaster": 1,
      "south_lancaster": 1,
      "little_york": 1,
      "quigley_catholic": 1,
      "archbishop_mcclellan": 1,
      "ocean_city": 1,
      "west_ocean_city": 1,
      "chapel_hill": 2,
      "durham": 2,
      "appalachia": 2,
      "crofton": 2,
      "st_peters": 2,
      "harding_central": 2,
      "lewis_catholic": 2,
      "providence": 3,
      "montpeiler": 3,
      "salem": 3,
      "concord": 3,
      "sacred_heart": 3,
      "ivy_prep": 3,
      "barton_lutheran": 3,
      "syracuse": 4,
      "upstate": 4,
      "empire_city": 4,
      "long_island_methodist": 4,
      "toronto_limited": 4,
      "mynsk": 4,
      "amariabi_international": 4,
      "grupenberg": 4,
      "ann_arbor": 5,
      "columbus": 5,
      "north_columbus": 5,
      "upper_peninsula": 5,
      "cleveland_carlysle": 5,
      "kenton": 5,
      "berkley": 5,
      "dillinger": 5,
      "evanston": 6,
      "wacker_west": 6,
      "two_rivers": 6,
      "d1_institute": 6,
      "falls_academy": 6,
      "knoxville": 7,
      "lexington": 7,
      "biloxi": 7,
      "mobile": 7,
      "myrtle_private": 7,
      "cardinal_conor": 7,
      "tallahassee": 8,
      "gainesville": 8,
      "deland": 8,
      "valdosta_valley": 8,
      "dade_academy": 8,
      "keys_high": 8,
      "hollywood_prep": 8,
      "iowa_academy": 9,
      "lawrence": 9,
      "ozark_centre": 9,
      "wash_u_prep": 9,
      "independence": 9,
      "burroughs": 9,
      "minot": 10,
      "ha_rushmore": 10,
      "grizzly_academy": 10,
      "east_rockies": 10,
      "rodeo_circuit": 10,
      "mt_simmons": 10,
      "border_academy": 10,
      "norman": 11,
      "abilene": 11,
      "amarillo_tech": 11,
      "ada": 11,
      "pan_handle_limited": 11,
      "southwest_miner": 11,
      "austin": 12,
      "austin_west": 12,
      "houston_jesuit": 12,
      "bayou_district": 12,
      "middletex": 12,
      "reyes_santiago": 12,
      "tucson": 13,
      "desert_regional": 13,
      "circus_circus": 13,
      "casino_row": 13,
      "huntington_canyon": 13,
      "rancho_estrada": 13,
      "boise": 14,
      "seattle_aaa": 14,
      "vancouver": 14,
      "rainier_central": 14,
      "couer_dalene": 14,
      "swoosh": 14,
      "tri_cities_prep": 14,
      "san_jose": 15,
      "cupertino": 15,
      "redwood_high": 15,
      "valley_high": 15,
      "stormwood": 15,
      "juneau_nome": 16,
      "mahala_alou": 16,
      "hana_road": 16,
      "melbourne_americas": 16,
      "pacific_all_stars": 16
  };

  function assignConferences(league) {
    var slots = {}, out = {};
    for (var c = 1; c <= 16; c++) slots[c] = 8;
    league.forEach(function (row) {
      var c = CONF_BY_SLUG[row[0]];
      if (c && slots[c] > 0) { out[row[0]] = c; slots[c]--; }
    });
    var open = [];
    for (var k = 1; k <= 16; k++) for (var i = 0; i < slots[k]; i++) open.push(k);
    league.forEach(function (row) {
      if (!out[row[0]]) out[row[0]] = open.shift();
    });
    return out;
  }
  var CONF_OF = assignConferences(LEAGUE);

  var ASSET_ROOT = 'FrontEnd/static/images/teams/';
  /* folder casing is not always the slug — IDA's folder is uppercase on disk
     while the file stem stays lowercase */
  var FOLDER_CASE = { ida: 'IDA' };
  function cardArt(slug) {
    return ASSET_ROOT + (FOLDER_CASE[slug] || slug) + '/' + slug + '_banner_card.webp';
  }
  var GENERAL_ART = ASSET_ROOT + 'general/general_banner_card.webp';

  var seed = 20260805;
  function rnd() { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; }

  /* NO mascot field on purpose. `team.mascot` is a real API field (teamPicker.js
     searches it), and every program's mascot is already painted into its
     banner_card artwork — Abilene are the Scorpions, Ada the Falcons. Printing
     a fabricated one next to the real logo is worse than printing none, so the
     logo carries it until the true values are wired from /teams. */

  var PROGRAMS = LEAGUE.map(function (row, idx) {
    var slug = row[0], name = row[1];
    var conf = CONF_OF[slug];
    return {
      id: idx, slug: slug, name: name, conf: conf,
      region: String.fromCharCode(65 + Math.floor((conf - 1) / 2)),
      geo: CONFERENCE_GEOGRAPHY[conf],
      art: cardArt(slug), artFallback: GENERAL_ART,
      talentRaw: 8600 + Math.floor(rnd() * 3400),
      prestigeRaw: 8 + Math.floor(rnd() * 91),
      heightRaw: rnd(), classRaw: rnd()
    };
  });

  /* rank bands, 26/25/26/25/26 — teamPicker.js BAND_CUTOFFS */
  var CUTS = [26, 51, 77, 102, 128];
  function bandBy(key, out) {
    PROGRAMS.slice().sort(function (a, b) {
      return b[key] - a[key] || (a.id - b.id);
    }).forEach(function (p, i) {
      var rank = i + 1, band = 5;
      for (var t = 0; t < CUTS.length; t++) { if (rank <= CUTS[t]) { band = t + 1; break; } }
      p[out] = band;
    });
  }
  bandBy('talentRaw', 'talent');
  bandBy('prestigeRaw', 'prestige');
  bandBy('heightRaw', 'size');
  bandBy('classRaw', 'experience');

  var CONF_GAMES = 14, NONCONF_GAMES = 13;
  function draw(games, mean, spread) {
    var w = Math.round(mean + (rnd() + rnd() + rnd() - 1.5) * spread);
    return Math.max(0, Math.min(games, w));
  }
  PROGRAMS.forEach(function (p) {
    /* band 1 → ~11 of 14, band 5 → ~3 of 14 */
    var cw = draw(CONF_GAMES, 13 - p.talent * 2, 2.6);
    /* non-conference is its own draw, loosely anchored to how the conference
       season went — independent enough that Conf and Overall carry different
       information, correlated enough that a .430 team can't go 1–12 */
    var nw = draw(NONCONF_GAMES, 6.4 + (cw - 7) * 0.55, 2.1);
    p.confWins = cw; p.ovWins = cw + nw;
    p.lastConf = cw + '–' + (CONF_GAMES - cw);
    p.lastOv = (cw + nw) + '–' + (CONF_GAMES + NONCONF_GAMES - cw - nw);
  });

  var GEOS = (function () {
    var f = {};
    Object.keys(CONFERENCE_GEOGRAPHY).forEach(function (k) {
      CONFERENCE_GEOGRAPHY[k].forEach(function (g) { f[g] = 1; });
    });
    return Object.keys(f).sort();
  })();

  window.GOBLeague = {
    TIERS: TIERS, PROGRAMS: PROGRAMS, GEOS: GEOS,
    CONFERENCE_GEOGRAPHY: CONFERENCE_GEOGRAPHY, CONF_NAMES: CONF_NAMES,
    cardArt: cardArt, GENERAL_ART: GENERAL_ART
  };
})();
