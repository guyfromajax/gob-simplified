/* FCC Roster + Recruiting tab mock — rendering + sorting. */
(function () {
  var R = window.GOB_ROSTER, RC = window.GOB_RECRUITS;
  var NAMES = {SC:'Scoring',SH:'Shooting',ID:'Inside Defense',OD:'Outside Defense',PS:'Passing',BH:'Ball Handling',RB:'Rebounding',ST:'Strength',AG:'Agility',ND:'Endurance',IQ:'Basketball IQ',FT:'Free Throws'};
  var GROUPS = [['OFFENSE',['SC','SH']],['DEFENSE',['ID','OD']],['SKILLS',['PS','BH']],['GRIT',['RB','ST']],['BODY',['AG','ND']],['MIND',['IQ','FT']]];
  var YEAR_ORDER = {HS:-1,JH:0,FR:1,SO:2,JR:3,SR:4,GR:5};
  var RT_BANDS = [[100,'A++','rt-elite'],[90,'A+','rt-elite'],[80,'A','rt-elite'],[70,'B+','rt-high'],[60,'B','rt-high'],[50,'C+','rt-mid'],[40,'C','rt-mid'],[30,'D','rt-low'],[-Infinity,'F','rt-low']];

  var st = {tab:'roster-tab', scope:'varsity', rSort:'RT', rDir:'desc', cSort:'RT', cDir:'desc'};
  function el(id){return document.getElementById(id);}
  function d(){return document.documentElement.dataset;}
  function band(v){return RT_BANDS.find(function(b){return v>=b[0];});}
  function tier(v){return v>=10?'is-elite':v>=7?'is-hi':v<=3?'is-lo':'';}
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}

  function posCell(p){return '<span class="pos" style="--pc:var(--pos-'+p.pos+')">'+p.pos+'</span>';}
  function rtCell(p){var c=band(p.rt),o=band(p.rtPot);return '<span class="rt" title="Current rating → potential"><b class="'+c[2]+'">'+c[1]+'</b><i class="'+o[2]+'">'+o[1]+'</i></span>';}
  function tiles(p){
    return '<div class="grid">'+GROUPS.map(function(g){
      return '<div class="pair">'+g[1].map(function(k){var v=p.attrs[k];
        return '<span class="tile '+tier(v)+'" title="'+NAMES[k]+': '+v+'"><u>'+k+'</u><s>'+v+'</s></span>';}).join('')+'</div>';
    }).join('')+'</div>';
  }
  function tilesHead(sort,dir){
    return '<th class="attrs head"><div class="grid">'+GROUPS.map(function(g){
      return '<div class="pair"><span class="grp">'+g[0]+'</span>'+g[1].map(function(k){
        return '<button class="abbr'+(sort===k?' is-sorted':'')+'" data-dir="'+dir+'" data-attr="'+k+'" title="'+NAMES[k]+'">'+k+'</button>';
      }).join('')+'</div>';
    }).join('')+'</div></th>';
  }
  function h(key,sort,dir,cls){
    var c=((cls||'')+(sort===key?' is-sorted':'')).trim();
    return ' data-sort="'+key+'"'+(c?' class="'+c+'"':'')+' data-dir="'+dir+'"';
  }
  function sortList(list,key,dir,extra){
    var sign=dir==='desc'?-1:1;
    function val(p){
      if(key==='name')return p.name;
      if(key==='RT')return p.rt;
      if(key==='pos')return ['PG','SG','SF','PF','C'].indexOf(p.pos);
      if(key==='year')return YEAR_ORDER[p.year]!=null?YEAR_ORDER[p.year]:0;
      if(key==='height')return p.heightIn;
      if(key==='weight')return p.weight;
      if(extra&&extra[key])return extra[key](p);
      return p.attrs[key]||0;
    }
    return list.slice().sort(function(a,b){
      var x=val(a),y=val(b);
      return typeof x==='string'?sign*x.localeCompare(y):sign*(x-y);
    });
  }

  /* ── Roster tab ── */
  function rosterWho(p){
    var flags='';
    if(p.name==='Trent Athens'||p.name==='Kent McManus')flags+='<span class="flag gr">GR</span>';
    if(p.name==='Omar Nola')flags+='<span class="flag ptp">PTP</span>';
    return '<div class="who"><span class="jersey">'+(p.jersey==='—'?'':p.jersey)+'</span><a class="nm" href="#">'+esc(p.name)+'</a>'+flags+'</div>';
  }
  function rosterTable(list){
    var s=st.rSort,dir=st.rDir;
    var head='<tr><th'+h('name',s,dir,'c-name')+'>Player</th><th'+h('RT',s,dir,'c-rt')+'>' + '<span class="lbl">RT</span><span class="cap">cur → pot</span>' + '</th>'+
      '<th'+h('pos',s,dir)+'>POS</th><th'+h('year',s,dir)+'>YR</th><th'+h('height',s,dir)+'>HT</th><th'+h('weight',s,dir)+'>WT</th>'+
      tilesHead(s,dir)+'</tr>';
    var body=sortList(list,s,dir).map(function(p){
      return '<tr><td class="c-name">'+rosterWho(p)+'</td><td class="c-rt">'+rtCell(p)+'</td><td>'+posCell(p)+
        '</td><td class="yr">'+p.year+'</td><td class="dim">'+p.height+'</td><td class="dim">'+p.weight+
        '</td><td class="attrs">'+tiles(p)+'</td></tr>';
    }).join('');
    return '<table><thead>'+head+'</thead><tbody>'+body+'</tbody></table>';
  }
  function renderRoster(){
    var scoped = d().ps==='scope';
    var list = scoped ? (st.scope==='varsity'?R.players:R.squad) : R.players;
    el('roster-surface').innerHTML = rosterTable(list);
    el('roster-scope').hidden = !scoped;
    el('roster-count').textContent = list.length + ' players';
    document.querySelectorAll('#roster-scope .pill').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.dataset.scope===st.scope));
    });
    if(!scoped) el('ps-surface').innerHTML = rosterTable(R.squad);
  }

  /* ── Recruits tab ── */
  function leanCell(r){
    if(!r.leanRank) return '<span class="recruit-stand-chip">NOT ON LIST</span>';
    return '<div class="lean-b">'+r.leanSlots.map(function(tok,i){
      var you = tok==='YOU', open = tok==='Open';
      return '<div class="lb-slot'+(you?' is-you':'')+(open?' is-open':'')+'"><span class="rk">#'+(i+1)+
        '</span><span class="lb-tok">'+(you?'YOU':esc(tok))+'</span></div>';
    }).join('')+'</div>';
  }
  function recruitsTable(){
    var s=st.cSort,dir=st.cDir,folded=d().recruitid==='folded';
    var extra={homeRegion:function(p){return p.homeRegion;},archetype:function(p){return p.archetype;},lean:function(p){return p.leanRank?4-p.leanRank:0;}};
    var head='<tr><th'+h('name',s,dir,'c-name')+'>'+(folded?'<span class="lbl">Recruit</span><span class="sub-sorts"><button class="subsort'+(s==='homeRegion'?' is-sorted':'')+'" data-subsort="homeRegion" data-dir="'+dir+'">Region</button>·<button class="subsort'+(s==='archetype'?' is-sorted':'')+'" data-subsort="archetype" data-dir="'+dir+'">Archetype</button></span>':'Name')+'</th>'+
      (folded?'':'<th'+h('homeRegion',s,dir)+'>HOME REGION</th><th'+h('archetype',s,dir)+'>ARCHETYPE</th>')+
      '<th'+h('RT',s,dir,'c-rt')+'>' + '<span class="lbl">RT</span><span class="cap">cur → pot</span>' + '</th>'+
      '<th'+h('pos',s,dir)+'>POS</th><th'+h('height',s,dir)+'>HT</th><th'+h('weight',s,dir)+'>WT</th>'+
      tilesHead(s,dir)+'<th'+h('lean',s,dir)+'>CURRENT LEAN</th></tr>';
    var body=sortList(RC.recruits,s,dir,extra).map(function(r){
      var idCell = folded
        ? '<div class="who"><div class="id-stack"><a class="nm" href="#">'+esc(r.name)+'</a><span class="id-sub">'+esc(r.homeRegion)+' · <b>'+esc(r.archetype)+'</b></span></div></div>'
        : '<div class="who"><a class="nm" href="#">'+esc(r.name)+'</a></div>';
      return '<tr><td class="c-name">'+idCell+'</td>'+
        (folded?'':'<td class="dim">'+esc(r.homeRegion)+'</td><td class="dim">'+esc(r.archetype)+'</td>')+
        '<td class="c-rt">'+rtCell(r)+'</td><td>'+posCell(r)+'</td><td class="dim">'+r.height+'</td><td class="dim">'+r.weight+
        '</td><td class="attrs">'+tiles(r)+'</td><td>'+leanCell(r)+'</td></tr>';
    }).join('');
    return '<table><thead>'+head+'</thead><tbody>'+body+'</tbody></table>';
  }
  function renderRecruits(){
    el('recruits-surface').innerHTML = recruitsTable();
    el('recruits-count').textContent = RC.recruits.length + ' recruits';
  }

  function render(){ renderRoster(); renderRecruits(); }
  window.GOB_FCC_RENDER = render;

  document.addEventListener('click', function(e){
    var tabBtn = e.target.closest('.tab-buttons button:not(.is-inert)');
    if(tabBtn){
      st.tab = tabBtn.dataset.tab;
      document.querySelectorAll('.tab-buttons button').forEach(function(b){b.classList.toggle('active', b.dataset.tab===st.tab);});
      document.querySelectorAll('.tab-content').forEach(function(c){c.classList.toggle('active', c.id===st.tab);});
      return;
    }
    var scopeBtn = e.target.closest('#roster-scope .pill');
    if(scopeBtn){ st.scope = scopeBtn.dataset.scope; renderRoster(); return; }
    var inRecruits = !!e.target.closest('#recruits-tab');
    var sortKey = null;
    var sub = e.target.closest('.subsort');
    if(sub) sortKey = sub.dataset.subsort;
    var abbr = e.target.closest('.abbr');
    if(!sortKey && abbr) sortKey = abbr.dataset.attr;
    if(!sortKey && !abbr) { var th = e.target.closest('th[data-sort]'); if(th) sortKey = th.dataset.sort; }
    if(!sortKey) return;
    if(inRecruits){
      if(st.cSort===sortKey) st.cDir = st.cDir==='desc'?'asc':'desc';
      else { st.cSort=sortKey; st.cDir = (sortKey==='name'||sortKey==='homeRegion'||sortKey==='archetype')?'asc':'desc'; }
      renderRecruits();
    } else {
      if(st.rSort===sortKey) st.rDir = st.rDir==='desc'?'asc':'desc';
      else { st.rSort=sortKey; st.rDir = sortKey==='name'?'asc':'desc'; }
      renderRoster();
    }
  });

  el('team-logo').src = 'FrontEnd/static/images/teams/'+R.team.slug+'/'+R.team.slug+'_banner_card.webp';
  el('fcc-record-label').textContent = 'Record: '+R.team.record;
  render();
})();
