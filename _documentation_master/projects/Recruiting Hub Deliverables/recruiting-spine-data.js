/* Recruiting Hub — Spine (D1) mock data.
   Extends the shape in recruiting-data.js with a real ranked lean model,
   a Year column, and curated examples for the lean-object state gallery.
   Exposes window.SpineData = { ... } */
(function () {
  const TEAM_NAME = 'Whitnall Pirates';
  const TEAM_ABBR = 'WHT';

  const REGIONS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
  const REGION_NAMES = {
    A: 'Northgate', B: 'Bay Cities', C: 'Piedmont', D: 'Delta',
    E: 'High Plains', F: 'Gulf Coast', G: 'Great Lakes', H: 'Cascade'
  };
  const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
  const YEARS = ['FR', 'SO', 'JR', 'JH'];
  const ARCHETYPES = [
    'Five-Star', 'Four-Star', 'All-Around Scorer', 'Classic C', 'Classic PF',
    'Classic SG', 'Classic PG', 'Inside Defender', 'Outside Defender',
    'Sharpshooter', 'Slasher', 'Floor General', 'Stretch Big', 'Rebounder'
  ];
  const FIRST = ['Jere','Julius','Dorian','Joseluis','Jesse','Nick','Sheldon','Scott','Mark','Vihaan','Devon','Marcus','Tariq','Bo','Cason','Elias','Finley','Greer','Holden','Ira','Jaden','Kai','Levi','Maddox','Nash','Otis','Pierce','Quinn','Reece','Silas','Tate','Uriah','Vance','Wells','Xavi','Yusuf','Zane','Asher','Booker','Cyrus','Dax','Ezra','Felix','Garrett','Heath','Idris','Jonah','Knox','Lance','Miles'];
  const LAST = ['Lu','Rasmussen','Burke','Parsons','Nash','Vance','Arellano','Bernal','Beck','Wells','Bartlett','Hayes','Cole','Drake','Ellis','Foster','Grant','Hill','Ingram','Jensen','Kerr','Lyons','Mason','North','Oakley','Pace','Quill','Rhodes','Stark','Thorpe','Underwood','Vega','Walsh','Yates','Abbott','Briggs','Crane','Dunn','Easton','Finch','Glass','Hart','Iverson','Jacobs','Kerns','Lloyd','Mercer','Noble','Owens','Page'];

  // Rival schools + stable 3-letter abbreviations
  const RIVALS = {
    'Ivy Prep': 'IVY', 'Sacred Heart': 'SAC', 'Hardwood Fields': 'HWF',
    'Bentley-Truman': 'BEN', 'Four Corners': 'FCR', 'Casino Row': 'CAS',
    'Lancaster': 'LAN', 'Nickel Beach': 'NKB', 'Garden Elites': 'GDN',
    'Concord': 'CON', "Queen's Guard": 'QNG', 'Morristown': 'MOR'
  };
  const RIVAL_NAMES = Object.keys(RIVALS);
  function abbr(team) {
    if (team === TEAM_NAME) return TEAM_ABBR;
    return RIVALS[team] || team.slice(0, 3).toUpperCase();
  }

  const ATTR_KEYS = ['SC','SH','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT'];

  function rand(seed) {
    let s = seed % 233280;
    return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  }
  const pick = (r, arr) => arr[Math.floor(r() * arr.length)];
  const attr = (r) => Math.max(0, Math.min(8, Math.floor(r() * 9)));

  // recruit RT scale (JH recruits)
  function rtTier(rt) {
    if (rt >= 50) return 'elite';
    if (rt >= 40) return 'high';
    if (rt >= 30) return 'mid';
    return 'low';
  }

  // Build the lean object. `leans` is an ordered array (index 0 = rank #1),
  // each entry = { team } or { open:true }. `locked` marks a loyal/hard target.
  function makeLeans(r, mode) {
    let leans = [];
    let locked = false;
    const other = () => pick(r, RIVAL_NAMES);
    switch (mode) {
      case 'you1': // you are #1
        leans = [{ team: TEAM_NAME }, { team: other() }, { team: other() }];
        break;
      case 'you2': // you are #2
        leans = [{ team: other() }, { team: TEAM_NAME }, { team: other() }];
        break;
      case 'you3': // you are #3
        leans = [{ team: other() }, { team: other() }, { team: TEAM_NAME }];
        break;
      case 'you2open': // you #2, third slot open
        leans = [{ team: other() }, { team: TEAM_NAME }, { open: true }];
        break;
      case 'others': // full list, no you
        leans = [{ team: other() }, { team: other() }, { team: other() }];
        break;
      case 'allopen':
        leans = [{ open: true }, { open: true }, { open: true }];
        break;
      case 'partial':
        leans = [{ team: other() }, { open: true }];
        break;
      case 'single':
        leans = [{ team: other() }];
        break;
      case 'singleyou':
        leans = [{ team: TEAM_NAME }];
        break;
      case 'locked': // loyal / hard target — locked to a rival #1
        leans = [{ team: other() }, { team: other() }];
        locked = true;
        break;
      case 'none': // no leans declared yet (early-season quiet)
        leans = [];
        break;
      default:
        leans = [{ open: true }, { open: true }, { open: true }];
    }
    // dedupe rival collisions so a list never shows the same rival twice
    const seen = new Set();
    leans.forEach(s => {
      if (s.team && s.team !== TEAM_NAME) {
        while (seen.has(s.team)) s.team = other();
        seen.add(s.team);
      }
    });
    const yourIndex = leans.findIndex(s => s.team === TEAM_NAME);
    return {
      leans,
      locked,
      yourRank: yourIndex === -1 ? null : yourIndex + 1,
      leansToUser: yourIndex !== -1
    };
  }

  function makeRecruit(r, i, forceMode) {
    const fn = pick(r, FIRST), ln = pick(r, LAST);
    const pos = pick(r, POSITIONS);
    const region = pick(r, REGIONS);
    const year = pick(r, YEARS);
    const arch = pick(r, ARCHETYPES);
    const ft = 5 + Math.floor(r() * 2);
    const inch = Math.floor(r() * 12);
    const weight = 160 + Math.floor(r() * 80);
    const rt = 26 + Math.floor(r() * 32); // 26-57

    let mode = forceMode;
    if (!mode) {
      const lr = r();
      if (lr < 0.16) mode = 'you1';
      else if (lr < 0.24) mode = r() < 0.5 ? 'you2' : 'you3';
      else if (lr < 0.30) mode = 'you2open';
      else if (lr < 0.34) mode = 'singleyou';
      else if (lr < 0.50) mode = 'others';
      else if (lr < 0.58) mode = 'locked';
      else if (lr < 0.68) mode = 'partial';
      else if (lr < 0.78) mode = 'single';
      else if (lr < 0.90) mode = 'allopen';
      else mode = 'none';
    }
    const lean = makeLeans(r, mode);

    const rec = {
      id: 'r' + i,
      name: fn + ' ' + ln,
      pos, region, year, archetype: arch,
      height: ft + "'" + inch + '"',
      heightInches: ft * 12 + inch,
      weight, rt, rtTier: rtTier(rt),
      leanMode: mode,
      ...lean
    };
    ATTR_KEYS.forEach(k => { rec[k] = attr(r); });
    // a few "new lean" / "lost" flags for the passive-phase story strip
    rec.newLean = false; rec.lost = false;
    return rec;
  }

  // ---- The pool: ~52 recruits spread across regions ----
  function buildPool() {
    const r = rand(41);
    const pool = [];
    for (let i = 0; i < 52; i++) pool.push(makeRecruit(r, i));
    // seed some weekly-story flags among leaning-to-you recruits
    const yours = pool.filter(x => x.leansToUser);
    yours.slice(0, 3).forEach(x => (x.newLean = true));
    // one recent loss (a recruit who dropped you) — synthesize
    const lostGuy = makeRecruit(rand(998), 900, 'others');
    lostGuy.name = 'Cason Drake'; lostGuy.region = 'C'; lostGuy.pos = 'SF';
    lostGuy.lost = true; lostGuy.rt = 47; lostGuy.rtTier = rtTier(47);
    pool.push(lostGuy);
    return pool;
  }

  // ---- Curated examples for the lean-object state gallery ----
  function example(mode, name, over) {
    const r = rand(mode.length * 7 + name.length * 3 + 5);
    const rec = makeRecruit(r, mode + '-' + name, mode);
    rec.name = name;
    return Object.assign(rec, over || {});
  }
  const leanStates = [
    { key: 'you1',      label: "You're #1",          hint: '≈8× odds — his top choice',        rec: example('you1', 'Marcus Vega', { pos: 'PF', rt: 54, region: 'B', year: 'JR' }) },
    { key: 'you2',      label: "You're #2",           hint: '≈4× odds — on his list',           rec: example('you2', 'Silas North', { pos: 'SG', rt: 48, region: 'A', year: 'SO' }) },
    { key: 'you3',      label: "You're #3",           hint: '≈2× odds — on his list',           rec: example('you3', 'Kai Foster', { pos: 'PG', rt: 41, region: 'D', year: 'JH' }) },
    { key: 'you2open',  label: "You're #2, slot open", hint: 'room to climb',                    rec: example('you2open', 'Wells Hart', { pos: 'C', rt: 50, region: 'F', year: 'FR' }) },
    { key: 'others',    label: 'Not in the picture',  hint: 'leans elsewhere — 1× odds',        rec: example('others', 'Dax Mercer', { pos: 'SF', rt: 45, region: 'G', year: 'JR' }) },
    { key: 'locked',    label: 'Loyal / hard target', hint: 'committed elsewhere — tough pull', rec: example('locked', 'Ezra Pace', { pos: 'C', rt: 52, region: 'E', year: 'SO' }) },
    { key: 'allopen',   label: 'All slots open',      hint: 'declared, undecided — up for grabs', rec: example('allopen', 'Tate Lloyd', { pos: 'SG', rt: 43, region: 'H', year: 'JH' }) },
    { key: 'partial',   label: 'Partially open',      hint: 'one lean, one open',               rec: example('partial', 'Booker Hill', { pos: 'PF', rt: 39, region: 'B', year: 'FR' }) },
    { key: 'single',    label: 'Single lean',         hint: 'one school only',                  rec: example('single', 'Miles Quill', { pos: 'PG', rt: 37, region: 'C', year: 'SO' }) },
    { key: 'none',      label: 'No leans yet',        hint: 'quiet — win games',                rec: example('none', 'Otis Beck', { pos: 'SF', rt: 34, region: 'A', year: 'JH' }) }
  ];

  window.SpineData = {
    TEAM_NAME, TEAM_ABBR, abbr,
    REGIONS, REGION_NAMES, POSITIONS, YEARS, ATTR_KEYS, ARCHETYPES,
    RIVAL_NAMES, rtTier,
    pool: buildPool(),
    leanStates
  };
})();
