/* Team Roster redesign — rendering + sorting. Vanilla, mirrors the production page's shape. */
(function () {
  var D = window.GOB_ROSTER;
  var NAMES = {SC:'Scoring',SH:'Shooting',ID:'Inside Defense',OD:'Outside Defense',PS:'Passing',BH:'Ball Handling',RB:'Rebounding',ST:'Strength',AG:'Agility',ND:'Endurance',IQ:'Basketball IQ',FT:'Free Throws'};
  // Pairs follow ATTR_GROUPS in team-roster-view.js (the card-back grouping).
  var GROUPS = [['OFFENSE',['SC','SH']],['DEFENSE',['ID','OD']],['SKILLS',['PS','BH']],['GRIT',['RB','ST']],['BODY',['AG','ND']],['MIND',['IQ','FT']]];
  var YEAR_ORDER = {JH:0,FR:1,SO:2,JR:3,SR:4,GR:5};
  var RT_BANDS = [[100,'A++','rt-elite'],[90,'A+','rt-elite'],[80,'A','rt-elite'],[70,'B+','rt-high'],[60,'B','rt-high'],[50,'C+','rt-mid'],[40,'C','rt-mid'],[30,'D','rt-low'],[-Infinity,'F','rt-low']];
  var STAT_GROUPS = [
    ['SCORING',['PTS']],['FIELD GOALS',['FGM','FGA','FG%']],['3-POINT',['3PTM','3PTA','3PT%']],
    ['FREE THROWS',['FTM','FTA','FT%']],['REBOUNDING',['OREB','DREB','TREB']],['PLAYMAKING',['AST']],
    ['DEFENSE',['STL','BLK','DEFA','DEF%']],['SCREENS',['SCRA','SCR%']],['MISTAKES',['F','TO']]
  ];
  var PCT = {'FG%':1,'3PT%':1,'FT%':1,'DEF%':1,'SCR%':1};

  var state = {scope:'varsity', view:'attributes', sort:'RT', dir:'desc'};
  function el(id){return document.getElementById(id);}
  function rows(){return state.scope === 'varsity' ? D.players : D.squad;}
  function rtBand(v){return RT_BANDS.find(function(b){return v >= b[0];});}
  function tier(v){return v >= 10 ? 'is-elite' : v >= 7 ? 'is-hi' : v <= 3 ? 'is-lo' : '';}
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}

  function statValue(p,k){
    var s = p.stats, gp = s.GP;
    if(k === 'FG%') return s.FGA ? s.FGM/s.FGA*100 : 0;
    if(k === '3PT%') return s['3PTA'] ? s['3PTM']/s['3PTA']*100 : 0;
    if(k === 'FT%') return s.FTA ? s.FTM/s.FTA*100 : 0;
    if(k === 'DEF%') return s.DEFA ? s.DEFS/s.DEFA*100 : 0;
    if(k === 'SCR%') return s.SCRA ? s.SCRS/s.SCRA*100 : 0;
    var raw = s[k] || 0;
    return document.documentElement.dataset.basis === 'pergame' ? raw/gp : raw;
  }
  function statText(p,k){
    var v = statValue(p,k);
    if(PCT[k]) return v.toFixed(1) + '%';
    return document.documentElement.dataset.basis === 'pergame' ? v.toFixed(1) : String(Math.round(v));
  }

  function sortValue(p,key){
    if(key === 'name') return p.name;
    if(key === 'RT') return p.rt;
    if(key === 'pos') return ['PG','SG','SF','PF','C'].indexOf(p.pos);
    if(key === 'year') return YEAR_ORDER[p.year] != null ? YEAR_ORDER[p.year] : 0;
    if(key === 'height') return p.heightIn;
    if(key === 'weight') return p.weight;
    if(p.attrs[key] != null) return p.attrs[key];
    return statValue(p,key);
  }
  function sorted(){
    var list = rows().slice(), k = state.sort, sign = state.dir === 'desc' ? -1 : 1;
    list.sort(function(a,b){
      var x = sortValue(a,k), y = sortValue(b,k);
      if(typeof x === 'string') return sign * x.localeCompare(y);
      return sign * (x - y);
    });
    return list;
  }

  function whoCell(p){
    var flags = '';
    if(p.name === 'Trent Athens' || p.name === 'Kent McManus') flags += '<span class="flag gr">GR</span>';
    if(p.name === 'Omar Nola') flags += '<span class="flag ptp">PTP</span>';
    return '<div class="who"><span class="jersey">' + (p.jersey === '—' ? '' : p.jersey) +
      '</span><a class="nm" href="#">' + esc(p.name) + '</a>' + flags + '</div>';
  }
  function rtCell(p){
    var cur = rtBand(p.rt), pot = rtBand(p.rtPot);
    return '<span class="rt" title="Current rating → potential"><b class="' + cur[2] + '">' + cur[1] +
      '</b><i class="' + pot[2] + '">' + pot[1] + '</i></span>';
  }
  function posCell(p){
    return '<span class="pos" style="--pc:var(--pos-' + p.pos + ')">' + p.pos + '</span>';
  }
  function tilesCell(p){
    return '<div class="grid">' + GROUPS.map(function(g){
      return '<div class="pair">' + g[1].map(function(k){
        var v = p.attrs[k];
        return '<span class="tile ' + tier(v) + '" title="' + NAMES[k] + ': ' + v + '"><u>' + k + '</u><s>' + v + '</s></span>';
      }).join('') + '</div>';
    }).join('') + '</div>';
  }
  function hAttr(key, extraClass){
    var cls = ((extraClass || '') + (state.sort === key ? ' is-sorted' : '')).trim();
    return ' data-sort="' + key + '"' + (cls ? ' class="' + cls + '"' : '') + ' data-dir="' + state.dir + '"';
  }

  function renderAttributes(){
    var trailing = document.documentElement.dataset.rt === 'trail';
    var vitals = '<th' + hAttr('pos') + '>POS</th><th' + hAttr('year') + '>YR</th>' +
      '<th' + hAttr('height') + '>HT</th><th' + hAttr('weight') + '>WT</th>';
    var rtHead = '<th' + hAttr('RT','c-rt') + '>' + '<span class="lbl">RT</span><span class="cap">cur → pot</span>' + '</th>';
    var attrHead = '<th class="attrs head"><div class="grid">' + GROUPS.map(function(g){
      return '<div class="pair"><span class="grp">' + g[0] + '</span>' + g[1].map(function(k){
        return '<button class="abbr' + (state.sort===k?' is-sorted':'') + '" data-dir="' + state.dir + '" data-attr="' + k + '" title="' + NAMES[k] + '">' + k + '</button>';
      }).join('') + '</div>';
    }).join('') + '</div></th>';
    var head = '<tr>' +
      '<th' + hAttr('name','c-name') + '>Player</th>' +
      (trailing ? vitals + attrHead + rtHead : rtHead + vitals + attrHead) + '</tr>';

    var body = sorted().map(function(p){
      var cells = {
        rt:'<td class="c-rt">' + rtCell(p) + '</td>',
        vitals:'<td>' + posCell(p) + '</td><td class="yr">' + p.year + '</td><td class="dim">' + p.height + '</td><td class="dim">' + p.weight + '</td>',
        attrs:'<td class="attrs">' + tilesCell(p) + '</td>'
      };
      return '<tr><td class="c-name">' + whoCell(p) + '</td>' +
        (trailing ? cells.vitals + cells.attrs + cells.rt : cells.rt + cells.vitals + cells.attrs) + '</tr>';
    }).join('');

    el('surface').innerHTML = '<table class="roster"><thead>' + head + '</thead><tbody>' + body + '</tbody></table>';
  }

  function renderStats(){
    var cols = [];
    STAT_GROUPS.forEach(function(g){ g[1].forEach(function(k,i){ cols.push({k:k, first:i===0}); }); });
    var groupRow = '<tr class="groups"><th class="c-name"></th>' + STAT_GROUPS.map(function(g){
      return '<th class="g-start" colspan="' + g[1].length + '">' + g[0] + '</th>';
    }).join('') + '</tr>';
    var colRow = '<tr class="cols"><th' + hAttr('name','c-name') + '>Player</th>' + cols.map(function(c){
      return '<th' + hAttr(c.k, c.first ? 'g-start' : '') + '>' + c.k + '</th>';
    }).join('') + '</tr>';
    var body = sorted().map(function(p){
      return '<tr><td class="c-name">' + whoCell(p) + '</td>' + cols.map(function(c){
        return '<td class="' + (c.first?'g-start ':'') + (PCT[c.k]?'pct':'') + '">' + statText(p,c.k) + '</td>';
      }).join('') + '</tr>';
    }).join('');
    el('surface').innerHTML = '<table class="stats"><thead>' + groupRow + colRow + '</thead><tbody>' + body + '</tbody></table>';
  }

  function setSort(key){
    if(state.sort === key) state.dir = state.dir === 'desc' ? 'asc' : 'desc';
    else { state.sort = key; state.dir = key === 'name' ? 'asc' : 'desc'; }
    render();
  }

  function render(){
    if(state.view === 'attributes') renderAttributes(); else renderStats();
    el('five-strip').style.display = state.scope === 'varsity' ? '' : 'none';
    el('basis').hidden = state.view !== 'stats';
    document.querySelectorAll('#basis .seg').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.dataset.basis === document.documentElement.dataset.basis));
    });
    document.querySelectorAll('.scope .pill').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.dataset.scope === state.scope));
    });
    document.querySelectorAll('.views .tab').forEach(function(b){
      b.setAttribute('aria-selected', String(b.dataset.view === state.view));
    });
  }

  function renderFive(){
    el('five').innerHTML = D.startingFive.map(function(p){
      var s = p.stats, gp = s.GP;
      var pct = s.DEFA ? Math.round(s.DEFS/s.DEFA*100) : 0;
      var cur = rtBand(p.rt);
      var initials = p.name.split(' ').map(function(w){return w[0];}).join('');
      return '<article class="p5-card"><div class="p5-photo">' +
        '<span class="p5-pos">' + p.pos + '</span>' +
        '<span class="p5-rt-badge ' + cur[2] + '">' + cur[1] + '</span>' +
        '<span class="p5-initials">' + initials + '</span>' +
        '</div><div class="p5-body"><div class="p5-namerow"><div class="p5-ident">' +
        '<div class="p5-name">' + esc(p.name) + '</div>' +
        '<div class="p5-bio">' + p.year + ' · ' + p.height + ' · ' + p.weight + ' lb</div>' +
        '</div><span class="p5-jersey">#' + p.jersey + '</span></div>' +
        '<div class="p5-stats">' +
        '<div class="p5-stat"><span class="sv">' + (s.PTS/gp).toFixed(1) + '</span><span class="sl">PPG</span></div>' +
        '<div class="p5-stat"><span class="sv">' + (s.TREB/gp).toFixed(1) + '</span><span class="sl">RPG</span></div>' +
        '<div class="p5-stat"><span class="sv">' + (s.AST/gp).toFixed(1) + '</span><span class="sl">APG</span></div>' +
        '<div class="p5-stat"><span class="sv">' + pct + '%</span><span class="sl">DEF</span></div>' +
        '</div></div></article>';
    }).join('');
  }

  document.addEventListener('click', function(e){
    var pill = e.target.closest('.scope .pill');
    if(pill){ state.scope = pill.dataset.scope; render(); return; }
    var tab = e.target.closest('.views .tab');
    if(tab){ state.view = tab.dataset.view; state.sort = state.view === 'stats' ? 'PTS' : 'RT'; state.dir = 'desc'; render(); return; }
    var seg = e.target.closest('#basis .seg');
    if(seg){ document.documentElement.dataset.basis = seg.dataset.basis; render(); return; }
    var abbr = e.target.closest('.abbr');
    if(abbr){ setSort(abbr.dataset.attr); return; }
    var th = e.target.closest('th[data-sort]');
    if(th){ setSort(th.dataset.sort); }
  });

  window.GOB_ROSTER_RENDER = render;
  var team = D.team;
  el('team-name').textContent = team.name;
  el('crest-art').src = 'FrontEnd/static/images/teams/' + team.slug + '/' + team.slug + '_banner_card.webp';
  el('m-record').textContent = team.record;
  el('m-conf').textContent = team.standing;
  el('scope-varsity-n').textContent = D.players.length;
  el('scope-squad-n').textContent = D.squad.length;
  renderFive();
  render();
})();
