/* Ch7 Home Base + Trophy Case preview renderer. Sample values are illustrative. Not product code. */
(function(){
var C=window.CH7,q=C.q,e=C.esc,T=C.TEAMS;
var P={
lawrence:{t:'lawrence',season:3,week:14,phase:'Regular season',rec:'16–5',rank:'#14',conf:'2nd',next:'at #21 Four Corners',nextWk:15},
chapel:{t:'chapel',season:1,week:6,phase:'Regular season',rec:'4–2',rank:'#37',conf:'4th',next:'vs Maple Ridge',nextWk:7}
};
var STATES={
first:{slots:[null,null]},
one:{slots:['lawrence',null],off:['chapel',null]},
two:{slots:['lawrence','chapel']},
live:{slots:['lawrence','chapel'],live:'lawrence'}
};
var TROPHIES=[
{m:'N',k:'gold',t:'National Champions',s:'Lawrence · Season 2'},
{m:'R',k:'gold',t:'Region B Champions',s:'Lawrence · Season 2'},
{m:'C',k:'gold',t:'Conference A2 Champions',s:'Lawrence · Season 1'},
{m:'S',k:'ms',t:'First signing class',s:'Lawrence · Season 1'},
{m:'A',k:'ms',t:'Systems Coach',s:'Coach archetype'}
];
function topbar(net,up){
return '<header class="hb-top"><div class="hb-mark"><b>Geeked-Out Basketball</b><span>Home Base</span></div>'+(up?'<a class="up" href="home-base.html?net=offline&s=two'+(C.d==='1920'?'&d=1920':'')+'"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M10 3 5 8l5 5"/></svg>Home Base</a>':'')+'<div class="hb-sp"></div><div class="hb-acct">'+(net==='online'?'<span class="hb-conn"><i></i>Online</span><b>Coach Demo</b><button class="hb-tl">Log Out</button>':'<span class="hb-conn off"><i></i>Offline · saves on this computer</span><b>Coach</b>')+'</div></header>';
}
function door(key,o){
var p=P[key],t=T[p.t],live=o.live===key,primary=o.primary===key,green=primary;
var lab=live?'Resume Game':'Enter';
return '<div class="door'+(o.hover?' is-hover':'')+'" role="link" tabindex="0" aria-label="Enter '+e(t.name)+'" style="--tc:'+t.tc+'"><div class="door-art"><img src="'+t.art+'" alt="">'+(primary?'<span class="door-tag">Last played</span>':'')+(live?'<div class="door-live"><i></i>Game in progress <span>· Week '+p.nextWk+'</span></div>':'')+'</div><div class="door-i"><div style="min-width:0"><div class="door-n">'+e(t.name)+'</div><div class="door-m">Season '+p.season+'<i>·</i>Week '+p.week+'</div><div class="door-m" style="margin-top:0">'+(live?'In game <i>·</i>':'Next <i>·</i>')+e(p.next)+'</div></div><div class="door-nums"><div><b>'+p.rec+'</b><span>Record</span></div><div><b>'+p.rank+'</b><span>National</span></div></div>'+(green?'<button class="advance">'+lab+'</button>':'<button class="btn-ghost sm">'+lab+'</button>')+'</div></div>';
}
function vacant(any,n){
return '<div class="vacant"><b>'+(any?'Start Another Franchise':'Start Your Coaching Journey')+'</b><p>'+(any?'Slot '+n+' is open. Take over another program, or build your own.':'Take over one of 128 programs, or build your own in Team Builder.')+'</p><button class="btn-ghost sm">Find Your Program</button></div>';
}
function slots(o){
var any=o.slots.some(Boolean),h='';
o.slots.forEach(function(k,i){
var n='0'+(i+1),menu=o.ui==='menu'&&i===0;
h+='<div class="slot"><div class="slot-h"><b>'+n+'</b><i></i>'+(k?'<button class="slot-more'+(menu?' open':'')+'" aria-label="Program options, slot '+n+'" aria-haspopup="menu"'+(menu?' aria-expanded="true"':'')+'>···</button>':'')+'</div>'+(k?door(k,o):vacant(any,n))+(menu?'<div class="pop" role="menu"><button class="pop-i danger is-hover" role="menuitem">Delete program…</button></div>':'')+'</div>';
});
return h;
}
function left(o){
var used=o.slots.filter(Boolean).length;
return '<section class="hb-l"><div class="hb-h"><h2>Your Programs</h2><span>'+used+' of 2 slots</span></div><div class="slots">'+slots(o)+'</div><div class="hb-util"><a class="hb-link go">Tutorials</a><button class="hb-link">Settings</button><a class="hb-link go">FAQs</a>'+(o.net==='online'?'<span class="hb-ver">YouTube · X</span>':'')+'</div></section>';
}
/* online right zone: Find A Game + one tabbed panel (Around GOB ⇄ Leaderboard) */
var CA='../assets/cards/';
var AG=[
{c:'AlphaCoach',sn:4,t:'grizzly_academy',n:'Grizzly Academy',w:1,s:'81–74',v:'#6 Knoxville',rec:'12–3',rk:'#9',wk:14,nw:1},
{c:'hoopsnerd',sn:2,t:'durham',n:'Durham',w:1,s:'70–64',v:'Evanston',rec:'10–5',rk:'#17',wk:14,nw:1},
{c:'MikeD',sn:6,t:'empire_city',n:'Empire City',w:1,s:'77–59',v:'#31 Austin',rec:'14–1',rk:'#2',wk:15,nw:1},
{c:'BetaCoach',sn:1,t:'four_corners',n:'Four Corners',w:0,s:'62–68',v:'Boise',rec:'8–7',rk:'#41',wk:14,nw:1},
{c:'threeandd',sn:3,t:'lexington',n:'Lexington',w:1,s:'90–71',v:'Crimson County',rec:'13–2',rk:'#4',wk:13,nw:1},
{c:'CoachK2',sn:2,t:'knoxville',n:'Knoxville',w:0,s:'66–71',v:'#4 Lexington',rec:'11–4',rk:'#6',wk:14},
{c:'zonebuster',sn:5,t:'crimson_county',n:'Crimson County',w:1,s:'88–80',v:'Durham',rec:'9–6',rk:'#22',wk:12},
{c:'pnrfan',sn:1,t:'evanston',n:'Evanston',w:0,s:'59–63',v:'#2 Empire City',rec:'5–10',rk:'#88',wk:14},
{c:'fullcourt',sn:2,t:'boise',n:'Boise',w:1,s:'72–70',v:'Four Corners',rec:'7–8',rk:'#54',wk:11},
{c:'glasscleaner',sn:1,t:'austin',n:'Austin',w:0,s:'61–75',v:'Grizzly Academy',rec:'6–9',rk:'#70',wk:15},
{c:'backscreen',sn:3,t:'stormwood',n:'Stormwood',w:1,s:'68–55',v:'Chapel Hill',rec:'9–5',rk:'#28',wk:10},
{c:'dribbledrive',sn:1,t:'chapel_hill',n:'Chapel Hill',w:0,s:'55–68',v:'Stormwood',rec:'4–10',rk:'#96',wk:10}
];
function agc(r,me){
var art=CA+r.t+'.webp';
return '<article class="agc'+(me?' is-me':'')+'" aria-label="'+e(me?'You':r.c)+': '+e(r.n)+' '+(r.w?'beat':'lost to')+' '+e(r.v)+' '+r.s+'"><img class="agc-bg" src="'+art+'" alt=""><div class="agc-art"><img src="'+art+'" alt="">'+'<span class="agc-coach">'+(r.nw&&!me?'<i></i>':'')+e(me?'You':r.c)+'</span></div><div class="agc-b"><div class="agc-s"><span class="wl '+(r.w?'w':'l')+'">'+(r.w?'W':'L')+'</span><b>'+r.s+'</b><small>SN '+r.sn+'<i>·</i>WK '+r.wk+'</small></div><div class="agc-v"><em>'+(r.w?'def.':'lost to')+'</em> <b>'+e(r.v)+'</b></div><div class="agc-m">'+e(r.n)+'<i>·</i>'+r.rec+'<i>·</i>'+r.rk+' national</div></div></article>';
}
function right_on(o){
var me=o.slots.filter(Boolean).length>0,tab=o.tab==='lb'?'lb':'ag';
var cards=(me?agc({sn:3,t:'lawrence',n:'Lawrence',w:1,s:'78–71',v:'#21 Four Corners',rec:'16–5',rk:'#14',wk:14},1):'')+AG.slice(0,me?11:12).map(function(r){return agc(r,0);}).join('');
var newN=AG.filter(function(r){return r.nw;}).length;
var LB=[['MikeD','1,240',6],['hoopsnerd','1,105',4],['AlphaCoach','980',5],['CoachK2','912',2],['BetaCoach','870',1],['threeandd','844',3],['zonebuster','801',1],['fullcourt','776',0],['pnrfan','750',2],['backscreen','731',0],['glasscleaner','702',1],['dribbledrive','688',0],['courtvision','671',0],['boxout','655',1],['elbowjumper','640',0]];
var tiles=LB.slice(0,3).map(function(r,i){return '<div class="lbt"><i>'+(i+1)+'</i><div><b>'+r[0]+'</b><span>'+r[1]+'<small>GP</small></span></div></div>';}).join('');
var rows=LB.slice(3).map(function(r,i){return '<div class="ldb-r'+(i>=8?' x':'')+'"><span>'+(i+4)+'</span><span class="ldb-n"><span class="nm">'+r[0]+'</span></span><b>'+r[1]+'</b></div>';}).join('')+'<div class="ldb-r me"><span>'+(me?38:'—')+'</span><span class="ldb-n"><span class="nm">Coach Demo</span><em>You</em></span><b>'+(me?380:0)+'</b></div>';
return '<section class="hb-r"><div class="fag" aria-disabled="true"><div class="fag-t"><div class="eyebrow">Head to head · Online only</div><h3>Find A Game</h3><p>Your program against another coach’s program.</p></div><span class="soon"><i></i>Coming Soon</span></div>'+
'<div class="hbt"><div class="hbt-row"><div class="hbt-tabs" role="tablist"><button class="hbt-tb" role="tab" data-tab="ag" aria-selected="'+(tab==='ag')+'">Around GOB'+(tab==='lb'&&newN?'<span class="hbt-n">'+newN+'</span>':'')+'</button><button class="hbt-tb" role="tab" data-tab="lb" aria-selected="'+(tab==='lb')+'">Leaderboard</button></div><div class="hbt-tools">'+(tab==='ag'?'Latest results from every coach’s own league':'<div class="seg" role="radiogroup"><button class="on" role="radio" aria-checked="true">Geek Points</button><button role="radio" aria-checked="false">Titles</button></div>')+'</div></div>'+
'<div class="hbt-p" role="tabpanel"'+(tab==='ag'?'':' hidden')+'><div class="agc-g">'+cards+'</div></div>'+
'<div class="hbt-p" role="tabpanel"'+(tab==='lb'?'':' hidden')+'><div class="lbp">'+tiles+'</div><div class="lbl">'+rows+'</div><div class="sec-f"><a class="lnk">By team</a><a class="lnk">Coaching archetypes</a></div></div></div></section>';
}
/* offline right zone: Your Career — record, trophy case, top seasons (Geek Points). No remote calls. */
var SEASONS=[
{t:'lawrence',n:'Lawrence Eagles',sn:2,rec:'31–5',fin:'National Champions',gold:1,gp:'1,860'},
{t:'lawrence',n:'Lawrence Eagles',sn:1,rec:'22–10',fin:'Conference A2 Champions',gold:1,gp:'1,120'},
{t:'lawrence',n:'Lawrence Eagles',sn:3,rec:'16–5',ip:'Week 14',gp:'940'},
{t:'chapel_hill',n:'Chapel Hill Sky',sn:1,rec:'4–2',ip:'Week 6',gp:'140'}
];
function tops(list){
var h='';
list.forEach(function(r,i){h+='<div class="tsn"><i>'+(i+1)+'</i><span class="tsn-a"><img src="'+CA+r.t+'.webp" alt=""></span><div class="tsn-n"><b>'+e(r.n)+'</b><span>Season '+r.sn+'</span></div><span class="tsn-r">'+r.rec+'</span><span class="tsn-f'+(r.gold?' gold-t':'')+'">'+(r.ip?'<span class="ip">In progress · '+r.ip+'</span>':e(r.fin))+'</span><span class="tsn-g">'+r.gp+'<small>GP</small></span></div>';});
for(var j=list.length;j<5;j++)h+='<div class="tsn is-e"><i>'+(j+1)+'</i><span>'+(j===list.length?(list.length?'Your next season can land here':'Coach your first game and your season ranks here'):'')+'</span></div>';
return '<div class="tsn-l">'+h+'</div>';
}
function right_off(o){
var full=o.trophies,none=!o.primary,tro=full?TROPHIES:[];
var c=none?{rec:'0–0',titles:'0',seasons:'0',gp:'0'}:full?{rec:'73–22',titles:'3',seasons:'4',gp:'4,060',sub:'.770'}:{rec:'4–2',titles:'0',seasons:'1',gp:'140',sub:'.667'};
var hz=function(v,zero){return '<b'+(zero?' class="hollow"':'')+'>'+v+'</b>';};
var nums='<div class="cr-n"><div>'+hz(c.rec,none)+'<span>Career record'+(c.sub?' · '+c.sub:'')+'</span></div><div>'+hz(c.titles,c.titles==='0')+'<span>Titles</span></div><div>'+hz(c.seasons,none)+'<span>Seasons</span></div><div>'+hz(c.gp,none)+'<span>Geek Points</span></div></div>';
var shelfH=tro.length?'<div class="shelf">'+tro.map(function(x){return '<div class="tro"><span class="med '+x.k+'">'+x.m+'</span><div><b>'+e(x.t)+'</b><span>'+e(x.s)+'</span></div></div>';}).join('')+'</div>':'<div class="shelf">'+[['C','Conference','Champions'],['R','Region','Champions'],['N','National','Champions'],['S','First signing class','Milestone']].map(function(x){return '<div class="tro slot-e"><span class="med">'+x[0]+'</span><div><b>'+x[1]+'</b><span>'+x[2]+'</span></div></div>';}).join('')+'</div>';
var list=full?SEASONS:none?[]:[SEASONS[3]];
return '<section class="hb-r cr"><div><div class="hb-h"><h2>Your Career</h2><span>All programs · this computer</span></div>'+nums+'</div>'+(none?'<p class="cr-cap">Every game you coach, in any program, adds to these.</p>':'')+
'<div class="tcase" style="padding-top:0"><div class="sec-h"><h3>Trophy Case</h3>'+(tro.length?'<span>3 titles · 2 milestones</span>':'<span>Still to win</span>')+'<div class="r"><a class="lnk" href="trophy-case.html?s='+(tro.length?'populated':'empty')+(C.d==='1920'?'&d=1920':'')+'">'+(tro.length?'View all':'Open')+'</a></div></div>'+shelfH+'</div>'+
'<div class="sec"><div class="sec-h"><h3>Top Seasons</h3><span>Ranked by season Geek Points</span></div>'+tops(list)+'</div></section>';
}
function renderHome(){
var net=q.get('net')==='offline'?'offline':'online',s=STATES[q.get('s')]?q.get('s'):'first',st=STATES[s];
var sl=(net==='offline'&&st.off)?st.off:st.slots;
var o={net:net,slots:sl,live:st.live,ui:q.get('ui'),tab:q.get('tab'),primary:sl.filter(Boolean)[0]||null,trophies:net==='offline'&&(s==='two'||s==='live')};
var r=C.root();
function paint(){r.innerHTML='<div class="hb">'+topbar(net)+'<main class="hb-body">'+left(o)+(net==='online'?right_on(o):right_off(o))+'</main></div>'+(o.ui==='confirm'?'<div class="mm-scrim"><div class="cfm" role="alertdialog" aria-modal="true" aria-labelledby="cfm-t"><h3 id="cfm-t">Delete Lawrence Eagles?</h3><p>Slot 01 <em>· Season 3, Week 14</em>. This deletes the program and every season in it. It can’t be undone.</p><div class="cfm-f"><button class="btn-ghost sm" autofocus>Cancel</button><button class="btn-del">Delete Program</button></div></div></div>':'');}
paint();
r.addEventListener('click',function(ev){var t=ev.target.closest('[data-tab]');if(!t)return;o.tab=t.dataset.tab;paint();});
}
function renderTrophy(){
var full=q.get('s')!=='empty',r=C.root();
var c=full?{rec:'73–22',titles:3,seasons:4,progs:2}:{rec:'0–0',titles:0,seasons:0,progs:0,z:1};
function cn(v,l){return '<div class="cn'+(c.z?' z':'')+'"><b>'+v+'</b><span>'+l+'</span></div>';}
var titles=TROPHIES.filter(function(x){return x.k==='gold';}),ms=TROPHIES.filter(function(x){return x.k!=='gold';});
var seasons=full?[['Season 3','Lawrence Eagles','16–5','In progress · Week 14',0],['Season 1','Chapel Hill Sky','4–2','In progress · Week 6',0],['Season 2','Lawrence Eagles','31–5','National Champions',1],['Season 1','Lawrence Eagles','22–10','Conference A2 Champions',1]]:[];
var tbl=seasons.length?'<div class="tcard"><table class="tbl"><thead><tr><th class="l">Season</th><th class="l w">Program</th><th>Record</th><th class="l">Finish</th><th></th></tr></thead><tbody>'+seasons.map(function(s){return '<tr><td class="l b">'+s[0]+'</td><td class="l w">'+s[1]+'</td><td class="b">'+s[2]+'</td><td class="l '+(s[4]&&/Champ/.test(s[3])?'gold-t':'dim')+'">'+s[3]+'</td><td>'+(s[4]?'<a class="lnk">Review</a>':'<span class="qt">—</span>')+'</td></tr>';}).join('')+'</tbody></table></div>':'<div class="tc-empty"><b>No season reviews yet</b>Your first review is written when a season ends: record, titles, awards, best players and the class you signed.</div>';
r.innerHTML='<div class="hb">'+topbar('offline',1)+'<main class="tc"><div class="tc-head"><h1><small>Coach career · all programs</small>Trophy Case</h1>'+cn(c.rec,'Record')+cn(c.titles,'Titles')+cn(c.seasons,'Seasons')+cn(c.progs,'Programs')+'</div><div class="tc-col"><div class="sec"><div class="sec-h"><h3>Titles</h3>'+(full?'<span>'+titles.length+'</span>':'')+'</div></div>'+(full?'<div class="shelf">'+titles.map(function(x){return '<div class="tro"><span class="med gold lg">'+x.m+'</span><div><b>'+x.t+'</b><span>'+x.s+'</span></div></div>';}).join('')+'</div>':'<div class="shelf is-empty"><span class="med open lg"></span><span class="med open lg"></span><span class="med open lg"></span><p>Win your conference, your region or the national tournament. The title is kept here for good.</p></div>')+'<div class="sec"><div class="sec-h"><h3>Milestones</h3>'+(full?'<span>'+ms.length+'</span>':'')+'</div></div>'+(full?'<div class="shelf">'+ms.map(function(x){return '<div class="tro sm"><span class="med ms">'+x.m+'</span><div><b>'+x.t+'</b><span>'+x.s+'</span></div></div>';}).join('')+'</div>':'<div class="tc-empty">Firsts land here: your first signing class, first bracket, first coach archetype.</div>')+'</div><div class="tc-col"><div class="sec"><div class="sec-h"><h3>Season Reviews</h3><span>Every season, every program</span></div></div>'+tbl+'</div></main></div>';
}
window.CH7HB={renderHome:renderHome,renderTrophy:renderTrophy};
})();
