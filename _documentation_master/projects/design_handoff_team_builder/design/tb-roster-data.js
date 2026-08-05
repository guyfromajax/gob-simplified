/* GOB Team Builder — roster fixture data.
   Stands in for the server payload. Position grades and weight are
   SERVER-COMPUTED in production; the helpers here exist only so the
   prototype can demonstrate the on-release round trip. */
(function () {
  'use strict';

  var ATTRS = [
    { code: 'SC', name: 'Scoring',         cat: 'offense' },
    { code: 'SH', name: 'Shooting',        cat: 'offense' },
    { code: 'ID', name: 'Inside Defense',  cat: 'defense' },
    { code: 'OD', name: 'Outside Defense', cat: 'defense' },
    { code: 'PS', name: 'Passing',         cat: 'technical' },
    { code: 'BH', name: 'Ball Handling',   cat: 'technical' },
    { code: 'RB', name: 'Rebounding',      cat: 'technical' },
    { code: 'ST', name: 'Strength',        cat: 'physical' },
    { code: 'AG', name: 'Agility',         cat: 'physical' },
    { code: 'ND', name: 'Endurance',       cat: 'physical' },
    { code: 'IQ', name: 'Basketball IQ',   cat: 'intangibles' },
    { code: 'FT', name: 'Free Throws',     cat: 'intangibles' }
  ];

  var CATS = {
    offense:     { label: 'Offense',     color: '#f79420' },
    defense:     { label: 'Defense',     color: '#4a90d9' },
    technical:   { label: 'Technical',   color: '#7b5ea7' },
    physical:    { label: 'Physical',    color: '#aeb8cc' },
    intangibles: { label: 'Intangibles', color: '#d4a017' }
  };

  var POS = ['PG', 'SG', 'SF', 'PF', 'C'];
  var POS_COLOR = { PG: '#4A90D9', SG: '#7B5EA7', SF: '#3A8C4A', PF: '#C0392B', C: '#D4A017' };
  var CLASSES = ['FR', 'SO', 'JR', 'SR'];
  var CLASS_RANK = { FR: 1, SO: 2, JR: 3, SR: 4 }; // server-supplied in production

  function a(v) {
    var o = {};
    ATTRS.forEach(function (t, i) { o[t.code] = v[i]; });
    return o;
  }

  //            SC  SH  ID  OD  PS  BH  RB  ST  AG  ND  IQ  FT
  var ROSTER = [
    { n: 3,  name: 'Dorian Reese',     pos: 'PG', cls: 'SR', ht: 74, wt: 188, tone: 4, build: 'Lean',     wo: false, attrs: a([62,74,28,66,82,85,34,48,84,76,79,81]) },
    { n: 11, name: 'Kai Mbeki',        pos: 'SG', cls: 'JR', ht: 77, wt: 205, tone: 5, build: 'Athletic', wo: false, attrs: a([71,86,34,62,58,68,42,55,78,70,66,84]) },
    { n: 24, name: 'Silas Vance',      pos: 'SF', cls: 'SO', ht: 79, wt: 218, tone: 2, build: 'Athletic', wo: false, attrs: a([74,61,52,70,55,58,64,68,72,74,62,66]) },
    { n: 42, name: 'Aleksy Nowak',     pos: 'PF', cls: 'SR', ht: 81, wt: 241, tone: 1, build: 'Solid',    wo: false, attrs: a([76,42,78,54,44,40,82,84,58,72,70,58]) },
    { n: 50, name: 'Tobias Kruger',    pos: 'C',  cls: 'JR', ht: 84, wt: 262, tone: 2, build: 'Heavy',    wo: false, attrs: a([72,22,86,44,36,28,88,90,44,68,64,48]) },
    { n: 7,  name: 'Marquis Ealy',     pos: 'PG', cls: 'FR', ht: 72, wt: 176, tone: 5, build: 'Slight',   wo: false, attrs: a([54,62,24,55,74,79,30,42,86,68,58,70]) },
    { n: 15, name: 'Jonah Whitfield',  pos: 'SG', cls: 'SO', ht: 76, wt: 197, tone: 1, build: 'Lean',     wo: false, attrs: a([66,78,32,58,52,64,38,50,74,66,60,79]) },
    { n: 33, name: 'Emeka Duru',       pos: 'SF', cls: 'JR', ht: 80, wt: 228, tone: 6, build: 'Athletic', wo: false, attrs: a([70,48,62,72,50,52,70,74,68,76,66,60]) },
    { n: 4,  name: 'Rowan Petrie',     pos: 'PF', cls: 'FR', ht: 80, wt: 233, tone: 2, build: 'Solid',    wo: false, attrs: a([58,44,66,50,40,38,72,70,56,64,52,54]) },
    { n: 21, name: 'Cyrus Bellamy',    pos: 'C',  cls: 'SO', ht: 82, wt: 255, tone: 4, build: 'Heavy',    wo: false, attrs: a([64,26,76,42,34,30,80,82,46,62,58,44]) },
    { n: 8,  name: 'Deshawn Ivory',    pos: 'SG', cls: 'JR', ht: 75, wt: 192, tone: 5, build: 'Lean',     wo: false, attrs: a([62,72,30,60,56,66,36,48,76,70,62,74]) },
    { n: 31, name: 'Anders Holm',      pos: 'PF', cls: 'SR', ht: 82, wt: 247, tone: 1, build: 'Solid',    wo: false, attrs: a([60,52,70,48,46,42,74,76,52,66,68,62]) },
    { n: 45, name: 'Peter Lindqvist',  pos: 'SF', cls: 'FR', ht: 73, wt: 170, tone: 1, build: 'Slight',   wo: true,  attrs: a([18,22,12,16,20,24,14,19,26,21,15,23]) },
    { n: 52, name: 'Gabe Rourke',      pos: 'PG', cls: 'SO', ht: 71, wt: 165, tone: 3, build: 'Slight',   wo: true,  attrs: a([14,20,10,13,17,22,11,15,24,18,12,19]) },
    { n: 0,  name: 'Tunde Akindele',   pos: 'C',  cls: 'JR', ht: 78, wt: 224, tone: 6, build: 'Lean',     wo: true,  attrs: a([20,12,24,15,13,11,26,28,17,22,16,14]) }
  ];

  function total(attrs) {
    return ATTRS.reduce(function (s, t) { return s + attrs[t.code]; }, 0);
  }

  var PLAYERS = ROSTER.map(function (p, i) {
    return Object.assign({}, p, {
      id: i,
      attrs: Object.assign({}, p.attrs),
      base: Object.assign({}, p.attrs),   // inherited attribute values
      budget: total(p.attrs),             // inherited total — must be matched exactly
      baseHt: p.ht,
      baseCls: p.cls,
      baseWt: p.wt
    });
  });

  var HEIGHT_BUDGET = PLAYERS.reduce(function (s, p) { return s + p.baseHt; }, 0);
  var CLASS_BUDGET  = PLAYERS.reduce(function (s, p) { return s + CLASS_RANK[p.baseCls]; }, 0);

  /* ---- stand-ins for server-computed values ---- */

  var W = {
    PG: { PS: .22, BH: .22, AG: .14, SH: .12, IQ: .12, OD: .10, SC: .08 },
    SG: { SH: .26, SC: .18, AG: .14, BH: .12, OD: .12, IQ: .10, FT: .08 },
    SF: { SC: .20, SH: .16, OD: .14, AG: .12, RB: .12, ID: .10, IQ: .10, ST: .06 },
    PF: { SC: .18, RB: .20, ID: .20, ST: .16, OD: .10, IQ: .08, AG: .08 },
    C:  { ID: .26, RB: .24, ST: .20, SC: .16, IQ: .08, AG: .06 }
  };
  var HT_PULL = { PG: -0.9, SG: -0.5, SF: 0, PF: 0.7, C: 1.1 };
  var GRADES = ['F', 'D', 'D+', 'C-', 'C', 'C+', 'B-', 'B', 'B+', 'A-', 'A', 'A+', 'A++'];

  function gradeFor(pos, attrs, ht) {
    var w = W[pos], s = 0;
    for (var k in w) s += attrs[k] * w[k];
    s += HT_PULL[pos] * (ht - 77);
    var i = Math.round((s - 30) / 5);
    return GRADES[Math.max(0, Math.min(GRADES.length - 1, i))];
  }
  function gradesFor(attrs, ht) {
    var o = {};
    POS.forEach(function (p) { o[p] = gradeFor(p, attrs, ht); });
    return o;
  }
  function scaleColor(v) {
    if (v <= 40) return '#ff6d6d';
    if (v <= 60) return '#FFD700';
    if (v <= 80) return '#34EC27';
    return '#4A90D9';
  }
  function feetInches(inches) {
    return Math.floor(inches / 12) + "'" + (inches % 12) + '"';
  }

  var TONES = ['#e8c9a8', '#dcae86', '#c58f63', '#a06c44', '#77492c', '#4d2e1c'];
  var BUILDS = ['Slight', 'Lean', 'Athletic', 'Solid', 'Heavy'];

  /* 48 of the 450-image pool, enough to demonstrate sort-don't-filter */
  var POOL = [];
  (function () {
    var seed = 7;
    function rnd() { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; }
    for (var i = 0; i < 48; i++) {
      POOL.push({ id: i, tone: 1 + Math.floor(rnd() * 6), build: BUILDS[Math.floor(rnd() * 5)] });
    }
  })();

  window.GOBRoster = {
    ATTRS: ATTRS, CATS: CATS, POS: POS, POS_COLOR: POS_COLOR, CLASSES: CLASSES,
    CLASS_RANK: CLASS_RANK, PLAYERS: PLAYERS, HEIGHT_BUDGET: HEIGHT_BUDGET,
    CLASS_BUDGET: CLASS_BUDGET, GRADES: GRADES, TONES: TONES, BUILDS: BUILDS, POOL: POOL,
    total: total, gradesFor: gradesFor, scaleColor: scaleColor, feetInches: feetInches
  };
})();
