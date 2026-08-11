/* GOB Training Load Screen — league news wire fixtures.

   ── PAYLOAD SHAPE THE EXPERIENCE NEEDS ──────────────────────────────────────
   One consolidated object. Every graphic in the rotation is one key; the client
   rotates over whichever keys are present and non-empty, so a partially-filled
   payload degrades gracefully (a week with no schedule simply drops that card).

   {
     phase: 'preseason' | 'in_season',
     season: 1,
     week: 4,                       // week just completed for in_season
     top10: [                       // 10 entries, rank order
       { rank, team_slug, team_name, wins, losses, conference, region }
     ],
     leaders: {                     // 8 boards; key = board id
       pts | treb | ast | def_pct | stl | blk | tpm | fg_pct: [
         { rank, player_id, name, team_slug, team_name, value, display }
       ]                            // 10 entries; `display` is preformatted ("78.6%")
     },
     key_games: [                   // 10, sorted by rank_sum asc
       { away_rank, away_slug, away_name, home_rank, home_slug, home_name, rank_sum }
     ],
     preseason: {                   // only when phase === 'preseason'
       top10:   [{ rank, team_slug, team_name, last_record, conference, region }],
       marquee: [{ week, away_rank, away_slug, away_name, home_rank, home_slug, home_name }]
     }
   }

   Notes for plumbing:
   • team_slug is required — art resolves to
     /images/teams/{slug}/{slug}_banner_primary.jpg (fallback general_banner_primary.jpg).
   • player_id is required — headshot resolves via
     API_CONFIG.getPlayerImageUrl(player_id, { size: 'card' }), silhouette on error.
   • conference is the integer 1–16 from `team.conference`; region is the letter
     A–H derived from it — String.fromCharCode(65 + floor((conference - 1) / 2)),
     the same rule js/shared/teamPicker.js uses. Send both; don't re-derive client-side.
   • Qualifiers are applied server-side: def_pct needs ≥6 DEFA/g, fg_pct needs ≥7 FGA/g.
   • Ranks are the national rank at the time the payload is built.

   This file is fixture data standing in for that payload.
   ────────────────────────────────────────────────────────────────────────── */
(function (w) {
  'use strict';

  var NAMES = {
    abilene:"Abilene", ada:"Ada", amarillo_tech:"Amarillo Tech", appalachia:"Appalachia",
    archbishop_mcclellan:"Archbishop McClellan", austin_west:"Austin West",
    barton_lutheran:"Barton Lutheran", bayou_district:"Bayou District",
    bentley_truman:"Bentley-Truman", border_academy:"Border Academy", burroughs:"Burroughs",
    cardinal_conor:"Cardinal Conor", casino_row:"Casino Row", chambless_global:"Chambless Global",
    chapel_hill:"Chapel Hill", crimson_county:"Crimson County", crofton:"Crofton",
    decatur_dei:"DeCatur Dei", east_rockies:"East Rockies", four_corners:"Four Corners",
    grupenberg:"Grupenberg", hana_road:"Hana Road", houston_jesuit:"Houston Jesuit",
    ida:"IDA", iowa_academy:"Iowa Academy", keys_high:"Keys High", knoxville:"Knoxville",
    lancaster:"Lancaster", little_york:"Little York", mobile:"Mobile", monroe_hayes:"Monroe-Hayes",
    morristown:"Morristown", mt_simmons:"Mt. Simmons", mynsk:"Mynsk", nickel_beach:"Nickel Beach",
    ocean_city:"Ocean City", ozark_centre:"Ozark Centre", providence:"Providence",
    reyes_santiago:"Reyes Santiago", rodeo_circuit:"Rodeo Circuit", san_jose:"San Jose",
    south_lancaster:"South Lancaster", swoosh:"Swoosh", tri_cities_prep:"Tri-Cities Prep",
    tucson:"Tucson", two_rivers:"Two Rivers", valdosta_valley:"Valdosta Valley",
    wash_u_prep:"Wash U Prep", xavien:"Xavien"
  };
  function tn(slug) { return NAMES[slug] || slug; }

  /* team.conference (1–16). Prototype fixture: the values below follow the real
     CONFERENCE_GEOGRAPHY groupings in js/shared/teamPicker.js. Region is derived
     from it with the shipped rule. */
  var CONF = {
    houston_jesuit: 12, chapel_hill: 2, crimson_county: 7, iowa_academy: 9, crofton: 2,
    wash_u_prep: 9, bayou_district: 12, nickel_beach: 8, tucson: 13, san_jose: 15
  };
  function regionOf(conf) { return String.fromCharCode(65 + Math.floor((conf - 1) / 2)); }
  function confOf(slug) { return CONF[slug] || 1; }

  var FOLDER_CASE = { ida: 'IDA' };
  /* Production: '/images/teams/' + folder + '/' + slug + '_banner_primary.jpg'.
     The prototype points at the card-scale variant of the SAME chevron art that is
     already committed for all 128 programs (400×141 vs 1920×679, identical
     composition) so the page stays light — swap the stem for production. */
  function bannerArt(slug) {
    var folder = FOLDER_CASE[slug] || slug;
    return '/images/teams/' + folder + '/' + slug + '_banner_card.webp';
  }
  var BANNER_FALLBACK = '/images/teams/general/general_banner_card.webp';

  /* Production: API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' }) → R2.
     Unreachable from the prototype, so this resolves to nothing and the silhouette
     fallback renders — which is exactly the real loading/error path. */
  function headshotUrl(playerId) {
    return 'https://images.geekedoutbasketball.com/players/' + playerId + '/card.webp';
  }

  function teamRow(rank, slug, w_, l_) {
    var c = confOf(slug);
    return {
      rank: rank, team_slug: slug, team_name: tn(slug), wins: w_, losses: l_,
      conference: c, region: regionOf(c)
    };
  }
  var TOP10 = [
    teamRow(1, 'houston_jesuit', 3, 0), teamRow(2, 'chapel_hill', 3, 0),
    teamRow(3, 'crimson_county', 3, 0), teamRow(4, 'iowa_academy', 3, 0),
    teamRow(5, 'crofton', 3, 0), teamRow(6, 'wash_u_prep', 3, 0),
    teamRow(7, 'bayou_district', 3, 0), teamRow(8, 'nickel_beach', 3, 0),
    teamRow(9, 'tucson', 2, 1), teamRow(10, 'san_jose', 2, 1)
  ];

  function game(ar, as, hr, hs) {
    return {
      away_rank: ar, away_slug: as, away_name: tn(as),
      home_rank: hr, home_slug: hs, home_name: tn(hs), rank_sum: ar + hr
    };
  }
  var KEY_GAMES = [
    game(1, 'houston_jesuit', 7, 'bayou_district'),
    game(4, 'iowa_academy', 5, 'crofton'),
    game(2, 'chapel_hill', 9, 'tucson'),
    game(3, 'crimson_county', 11, 'burroughs'),
    game(6, 'wash_u_prep', 10, 'san_jose'),
    game(8, 'nickel_beach', 12, 'lancaster'),
    game(13, 'amarillo_tech', 14, 'bentley_truman'),
    game(15, 'border_academy', 16, 'knoxville'),
    game(17, 'cardinal_conor', 18, 'mobile'),
    game(19, 'four_corners', 20, 'little_york')
  ].sort(function (a, b) { return a.rank_sum - b.rank_sum; });

  /* [name, slug, value] → board rows. `fmt` builds the display string. */
  function board(rows, fmt) {
    return rows.map(function (r, i) {
      return {
        rank: i + 1, player_id: 'p' + (1000 + (i * 7) + r[0].length + r[1].length),
        name: r[0], team_slug: r[1], team_name: tn(r[1]),
        value: r[2], display: fmt ? fmt(r[2]) : String(r[2])
      };
    });
  }
  var pct = function (v) { return v.toFixed(1) + '%'; };

  var LEADERS = {
    pts: { id: 'pts', title: 'National Scoring Leaders', unit: 'PTS', kicker: 'Season totals · through week {W}',
      rows: board([
        ['Darnell Love','xavien',63], ['Xenon Fletcher','bentley_truman',59],
        ['Aaron Mingus','ocean_city',58], ['Jeffrey Jackson','four_corners',57],
        ['Charles Black','four_corners',56], ['Mose Hawkins','morristown',54],
        ['Tommy La','ocean_city',52], ['Derrick Smith','little_york',51],
        ['Rupert Holliday','ocean_city',49], ['Kwame Castor','morristown',48]
      ]) },
    treb: { id: 'treb', title: 'National Rebounding Leaders', unit: 'REB', kicker: 'Season totals · through week {W}',
      rows: board([
        ['Darnell Love','xavien',26], ['Neel Baldwin','south_lancaster',25],
        ['Marlin McDonough','xavien',24], ['AC Buford','little_york',22],
        ['Nate Reardon','xavien',21], ['Kwame Castor','morristown',20],
        ['Sal Guerrero','tucson',19], ['Emmett Voss','crofton',19],
        ['Boyd Ferrell','keys_high',18], ['Ike Sandoval','mynsk',17]
      ]) },
    ast: { id: 'ast', title: 'National Assist Leaders', unit: 'AST', kicker: 'Season totals · through week {W}',
      rows: board([
        ['Mose Hawkins','morristown',16], ['Xenon Fletcher','bentley_truman',16],
        ['Rupert Holliday','ocean_city',13], ['Alex Thomas','morristown',12],
        ['Kevin Nelson','morristown',12], ['Julian Poe','chapel_hill',11],
        ['Trey Vandenberg','providence',11], ['Omar Ellison','san_jose',10],
        ['Cass Whitfield','ida',10], ['Bobby Marchetti','swoosh',9]
      ]) },
    def_pct: { id: 'def_pct', title: 'National Defense Leaders', unit: 'DEF%', kicker: 'Minimum 6.0 DEFA per game to qualify',
      rows: board([
        ['Aaron Mingus','ocean_city',75.0], ['Nate Reardon','xavien',72.4],
        ['Silas Brandt','crofton',71.1], ['AC Buford','little_york',70.6],
        ['Marlin McDonough','xavien',69.8], ['Dane Kirilenko','iowa_academy',68.9],
        ['Boyd Ferrell','keys_high',68.2], ['Neel Baldwin','south_lancaster',67.5],
        ['Rico Alvarado','bayou_district',66.9], ['Emmett Voss','crofton',66.1]
      ], pct) },
    stl: { id: 'stl', title: 'National Steal Leaders', unit: 'STL', kicker: 'Season totals · through week {W}',
      rows: board([
        ['Derrick Smith','little_york',8], ['Cass Whitfield','ida',7],
        ['Alex Thomas','morristown',7], ['Julian Poe','chapel_hill',6],
        ['Rico Alvarado','bayou_district',6], ['Tommy La','ocean_city',6],
        ['Omar Ellison','san_jose',5], ['Bobby Marchetti','swoosh',5],
        ['Trey Vandenberg','providence',5], ['Dane Kirilenko','iowa_academy',5]
      ]) },
    blk: { id: 'blk', title: 'National Block Leaders', unit: 'BLK', kicker: 'Season totals · through week {W}',
      rows: board([
        ['Nate Reardon','xavien',4], ['Marlin McDonough','xavien',3],
        ['Neel Baldwin','south_lancaster',3], ['AC Buford','little_york',3],
        ['Kwame Castor','morristown',3], ['Silas Brandt','crofton',3],
        ['Ike Sandoval','mynsk',2], ['Sal Guerrero','tucson',2],
        ['Emmett Voss','crofton',2], ['Boyd Ferrell','keys_high',2]
      ]) },
    tpm: { id: 'tpm', title: 'National 3PT Leaders', unit: '3PM', kicker: 'Three-pointers made · through week {W}',
      rows: board([
        ['Xenon Fletcher','bentley_truman',10], ['Tommy La','ocean_city',9],
        ['Darnell Love','xavien',8], ['Derrick Smith','little_york',7],
        ['Aaron Mingus','ocean_city',6], ['Julian Poe','chapel_hill',6],
        ['Charles Black','four_corners',6], ['Omar Ellison','san_jose',5],
        ['Bobby Marchetti','swoosh',5], ['Kevin Nelson','morristown',5]
      ]) },
    fg_pct: { id: 'fg_pct', title: 'National FG% Leaders', unit: 'FG%', kicker: 'Minimum 7.0 FGA per game to qualify',
      rows: board([
        ['Aaron Mingus','ocean_city',78.6], ['Kwame Castor','morristown',64.3],
        ['Darnell Love','xavien',61.9], ['Neel Baldwin','south_lancaster',60.5],
        ['Sal Guerrero','tucson',59.4], ['Jeffrey Jackson','four_corners',58.8],
        ['Emmett Voss','crofton',57.7], ['Charles Black','four_corners',56.5],
        ['Ike Sandoval','mynsk',55.9], ['Silas Brandt','crofton',55.2]
      ], pct) }
  };

  var PRESEASON_TOP10 = [
    ['houston_jesuit','28-4'], ['crimson_county','27-5'], ['chapel_hill','26-6'],
    ['wash_u_prep','26-6'], ['iowa_academy','25-7'], ['bayou_district','24-8'],
    ['crofton','24-8'], ['tucson','23-9'], ['nickel_beach','23-9'], ['san_jose','22-10']
  ].map(function (r, i) {
    var c = confOf(r[0]);
    return {
      rank: i + 1, team_slug: r[0], team_name: tn(r[0]), last_record: r[1],
      conference: c, region: regionOf(c)
    };
  });

  var MARQUEE = [
    [3, 1, 'houston_jesuit', 2, 'crimson_county'], [5, 4, 'wash_u_prep', 3, 'chapel_hill'],
    [7, 6, 'bayou_district', 5, 'iowa_academy'], [9, 2, 'crimson_county', 7, 'crofton'],
    [11, 8, 'tucson', 1, 'houston_jesuit'], [13, 9, 'nickel_beach', 4, 'wash_u_prep'],
    [15, 3, 'chapel_hill', 6, 'bayou_district'], [17, 10, 'san_jose', 8, 'tucson'],
    [19, 5, 'iowa_academy', 2, 'crimson_county'], [21, 7, 'crofton', 1, 'houston_jesuit']
  ].map(function (r) {
    return {
      week: r[0], away_rank: r[1], away_slug: r[2], away_name: tn(r[2]),
      home_rank: r[3], home_slug: r[4], home_name: tn(r[4])
    };
  });

  w.GOBNewsWire = {
    phase: 'in_season', season: 1, week: 4,
    top10: TOP10, leaders: LEADERS, key_games: KEY_GAMES,
    preseason: { top10: PRESEASON_TOP10, marquee: MARQUEE },
    bannerArt: bannerArt, BANNER_FALLBACK: BANNER_FALLBACK, headshotUrl: headshotUrl
  };
})(window);
