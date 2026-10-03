/* Ch7 reward-ladder preview renderer: Office (weekly card), milestone modal, season peak. Sample values are illustrative. Not product code. */
(function(){
var C=window.CH7,q=C.q,e=C.esc,P=C.PORT,rt=C.rt,ad=C.ad;
function I(i){return ' style="--i:'+i+'"';}
/* ── WEEKLY card ── */
var WK={
win:{won:1,when:'Week 14 · Home',you:['#14','Lawrence',78],opp:['#21','Four Corners',71],hl:'Park’s 24 carry Lawrence past Four Corners',ld:['Player of the Game','Devin Park',24,9,5],
 b:[['National','#14','▲3',''],['Conference','2nd','▲1',''],['Record','16–5','',''],['Streak','W4','','']],
 g:[['Devin Park',[['SH',8,'▲1']]],['Isaiah Monroe',[['AG',7,'▲1'],['ND',6,'▲1']]],['Silas Kerr',[['ST',5,'▼1','dn']]]]},
loss:{won:0,when:'Week 14 · Away',you:['#14','Lawrence',64],opp:['#9','Maple Ridge',70],hl:'',ld:['Team leader','Devin Park',19,6,3],
 b:[['National','#17','▼3','dn'],['Conference','3rd','▼1','dn'],['Record','15–6','',''],['Streak','L1','','']],
 g:[['Isaiah Monroe',[['AG',7,'▲1']]],['Marcus Hale',[['PS',6,'▲1']]],['Silas Kerr',[['ST',5,'▼1','dn']]]],
 also:['Coach archetype','Systems Coach established']}
};
WK.gain=JSON.parse(JSON.stringify(WK.win));WK.gain.g[1]=['Isaiah Monroe',[['SH',8,'▲2','xg'],['AG',7,'▲1']]];WK.gain.xg=1;
WK.lossgain=JSON.parse(JSON.stringify(WK.loss));WK.lossgain.g[0]=['Isaiah Monroe',[['SH',8,'▲2','xg']]];WK.lossgain.xg=1;delete WK.lossgain.also;
function weekly(k){
var w=WK[k]||WK.win,won=w.won;
function row(t,me){var win=(me&&won)||(!me&&!won);return '<div class="sb2-r'+(win?' w':'')+'"><span class="sb2-n"><em>'+t[0]+'</em><span>'+t[1]+'</span></span><span class="sb2-p"'+(won?' data-to="'+t[2]+'"':'')+'>'+t[2]+'</span></div>';}
var h='<article class="wkc '+(won?'is-win':'is-loss')+'" aria-label="Since last week: '+(won?'win':'loss')+'">';
h+='<div class="wkc-k"><span class="wtag">'+(won?'WIN':'LOSS')+'</span><span class="wkc-when">'+w.when+'</span><a class="lnk">Box score</a></div>';
h+='<div class="sb2">'+row(w.you,1)+row(w.opp,0)+'</div>';
if(w.hl)h+='<a class="wkc-hl wi"'+I(0)+'>'+w.hl+'</a>';
h+='<div class="pg2 wi"'+I(1)+'><span class="portrait"><img src="'+P+'" alt=""></span><div class="pg2-id"><span class="eyebrow">'+w.ld[0]+'</span><a class="nm">'+w.ld[1]+'</a><div class="pg2-l"><div><b>'+w.ld[2]+'</b><span>PTS</span></div><div><b>'+w.ld[3]+'</b><span>REB</span></div><div><b>'+w.ld[4]+'</b><span>AST</span></div></div></div></div>';
h+='<div class="bdgs">'+w.b.map(function(b,i){return '<div class="bdg"'+I(i)+'><span>'+b[0]+'</span><div class="bdg-v"><b>'+b[1]+'</b>'+(b[2]?'<em class="'+b[3]+'">'+b[2]+'</em>':'')+'</div></div>';}).join('')+'</div>';
h+='<div class="wkc-tr wi"'+I(2)+'><div class="wkc-tr-h"><span class="sub-h">Training · this week</span>'+(w.xg?'<span class="xg-key">Exceptional gain</span>':'')+'</div>'+w.g.map(function(g){return '<div class="gn"><a class="nm">'+g[0]+'</a><div class="gn-c">'+g[1].map(function(c){return '<span class="gc '+(c[3]||'')+'" title="'+c[0]+'"><b>'+c[0]+'</b>'+ad(c[1])+'<i>'+c[2]+'</i></span>';}).join('')+'</div></div>';}).join('')+'</div>';
if(w.also)h+='<div class="wkc-also wi"'+I(3)+'><span>Also</span><b>'+w.also[1]+'</b><a class="lnk">View</a></div>';
h+='<div class="wkc-f"><a class="lnk">All changes</a></div></article>';
return h;
}
function countUp(root){
root.querySelectorAll('.sb2-p[data-to]').forEach(function(el){var to=+el.dataset.to,t0=null;el.textContent='0';setTimeout(function(){function f(t){if(!t0)t0=t;var p=Math.min(1,(t-t0)/600);el.textContent=Math.round(to*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f);}requestAnimationFrame(f);},120);});
}
/* ── Office columns 2–3 (existing components, shown for footprint) ── */
function col2(){
var st=[[1,'Harbor City','14–7','+88'],[2,'Lawrence','16–5','+71',1],[3,'Cedar Point','13–8','+40']];
return '<div class="card office-next"><div class="card-h"><h3>Next game</h3><span class="meta">Week 15 · Away</span></div><div class="nx-m"><span class="logo" style="--tc:#2F6B4F;width:40px;height:40px;font-size:22px">F</span><div><span class="nx-at">AT</span><a class="nx-name">21. Four Corners</a><span class="nx-sub">12–9 · Conference A2 (5th of 8)</span></div></div><div class="sub-h">Players to watch</div><div class="ptw"><a class="nm">Marcus Ruiz</a><span class="ptw-r">Top scorer</span><b>19.4</b><em>PPG</em></div><div class="ptw"><a class="nm">Dante Cole</a><span class="ptw-r">Top rebounder</span><b>9.1</b><em>RPG</em></div></div>'+
'<div class="card office-snap"><div class="card-h"><h3>Team snapshot</h3></div><div class="sn-g"><div class="sn-row"><span class="sn-l">Chemistry</span><span class="sn-v">18<i>/25</i></span></div><div class="meter"><i style="width:72%"></i></div></div><div class="sub-h">Moved most</div><div class="msr"><span>Fight</span><b>+2</b></div><div class="msr"><span>Discipline</span><b>−1</b></div></div>'+
'<div class="card"><div class="card-h"><h3>Conference A2 standings</h3><a class="lnk">Full standings</a></div><div class="st-t"><div class="st-r st-hd"><span></span><span>Team</span><span>W-L</span><span>Diff</span></div>'+st.map(function(r){return '<div class="st-r'+(r[4]?' me':'')+'"><span>'+r[0]+'</span><span class="st-n">'+r[1]+'</span><span>'+r[2]+'</span><span>'+r[3]+'</span></div>';}).join('')+'</div></div>';
}
function col3(){
var w=[['Jalen Brooks','SG','Moved Lawrence into his top three','',1],['Tre Watkins','C','Took a visit to Harbor City','dn',1],['Owen Castillo','PF','Lean on Lawrence held steady','fl',0],['Marcus Bell','PG','Lawrence climbed to 2nd on his list','',0],['Eli Navarro','SF','Cut his list to five, Lawrence still on it','fl',0],['Kobe Rhodes','G','Grizzly Academy passed Lawrence','dn',0]];
return '<div class="card office-wire"><div class="card-h"><h3>Recruiting wire</h3><span class="meta">6 updates</span></div>'+w.map(function(r){return '<div class="evr'+(r[4]?' new':'')+'"><span class="nw"></span><div class="evr-b"><div class="evr-1">'+r[0]+' <em>'+r[1]+'</em></div><div class="evr-2">'+r[2]+'</div></div><span class="dir '+r[3]+'">'+(r[3]==='dn'?'▼':r[3]==='fl'?'—':'▲')+'</span></div>';}).join('')+'</div>';
}
function office(k,arrive){
return '<div class="app" data-adv="PLAY NEXT GAME"><main class="main office-main"><div class="pv-strip"><span class="pv-step done"><i></i>Training</span><span class="pv-step done"><i></i>Game Plan</span><span class="pv-step next"><i></i>Play Next Game</span></div><div class="office'+(arrive?' wk-arrive':'')+'"><div class="office-col"><div class="office-h"><h2>Since last week</h2></div>'+weekly(k)+'</div><div class="office-col"><div class="office-h"><h2>This week</h2></div>'+col2()+'</div><div class="office-col"><div class="office-h"><a class="col-link"><h2>Recruiting →</h2></a></div>'+col3()+'</div></div></main></div>';
}
function boot(inner,after){
var r=C.root();r.style.setProperty('--team-primary','#8C1D40');r.innerHTML=inner;
var s=document.createElement('script');s.src='shell.js';s.onload=function(){if(after)after(r);};document.body.appendChild(s);
return r;
}
/* ── MILESTONE modal ── */
var REC=[['Jordan Price','PG · Region B','B','A−'],['Malik Stone','SF · Region B','B−','B+'],['Caleb Ortiz','C · Region D','C+','B'],['Andre Voss','SG · Region B','C','B−'],['Luis Marín','PF · Region A','C','C+']];
function initials(n){return n.split(' ').map(function(x){return x[0];}).join('');}
var MOM={
signing:{tone:'gold',k:'Signing Day',t:'Your class is signed',d:'Five recruits committed to Lawrence. They join the roster when Season 4 begins.',
 b:function(){return '<div class="rc-l wi"'+I(1)+'>'+REC.map(function(r){return '<div class="rc"><span class="av">'+initials(r[0])+'</span><div class="rc-n"><b>'+r[0]+'</b><span>'+r[1]+'</span></div>'+rt(r[2],r[3])+'</div>';}).join('')+'</div>';}},
archetype:{tone:'gold',k:'Coach archetype',t:'You’re a Systems Coach',d:'Your first twelve games set your coaching identity.',
 b:function(){return '<div class="arch wi"'+I(0)+'><span class="med gold" style="--ms:64px">S</span><p>Systems Coaches get more out of scheme installs, and their playbooks learn faster. Your archetype can still change as you coach.</p></div>';}},
bracket:{tone:'gold',k:'National tournament',t:'You’re in: 3 seed, Region B',d:'Selection is in. Lawrence opens the national tournament in Week 27.',link:'Full bracket',
 b:function(){return '<div class="seed wi"'+I(0)+'><div class="seed-n"><b>3</b><span>Seed</span></div><div class="mu"><div class="mu-r"><i>Round 1</i><span><span class="me"><b>#3 Lawrence</b></span><em>vs</em>#14 Harbor City</span><span>Week 27 · Home</span></div><div class="mu-r"><i>Round 2</i><span>Winner of #6 Cedar Point <em>/</em> #11 Oak Hollow</span><span>Week 28</span></div><div class="mu-r"><i>Round 3</i><span>Region B, top half</span><span>Week 29</span></div></div></div>';}},
elim:{tone:'quiet',k:'Season over',t:'Eliminated in the Region Semifinal',d:'Maple Ridge ended Lawrence’s run, 70–64. The season closes at 24–9.',
 b:function(){return '<div class="fin"><div class="fin-t"><b>Lawrence</b><span>#3 seed</span></div><div class="fin-s">64<i>–</i>70</div><div class="fin-t r"><b>Maple Ridge</b><span>#2 seed</span></div></div><div class="mm-sum"><div><b>24–9</b><span>Record</span></div><div><b>2nd</b><span>Conference A2</span></div><div><b>#18</b><span>National</span></div></div><p class="mm-d" style="margin-top:0;color:var(--text-60)">Signing Day is Week 35. Your season review follows it.</p>';}}
};
var QUEUES={signing:['signing','archetype'],bracket:['bracket'],elim:['elim']};
function modal(queue,i){
var m=MOM[queue[i]],n=queue.length,last=i===n-1;
var dots=n>1?'<div class="mq" aria-label="Moment '+(i+1)+' of '+n+'">'+queue.map(function(_,j){return '<i class="'+(j===i?'on':'')+'"></i>';}).join('')+'<span>'+(i+1)+' of '+n+'</span></div>':'';
return '<div class="mm is-'+m.tone+'" role="dialog" aria-modal="true" aria-labelledby="mm-t"><div class="mm-h"><div class="mm-k">'+m.k+'</div>'+dots+'<button class="mm-x" aria-label="Close. Remaining moments wait for your next visit.">×</button></div><div class="mm-c"><div><h2 class="mm-t" id="mm-t">'+m.t+'</h2><p class="mm-d">'+m.d+'</p></div>'+m.b()+'</div><div class="mm-f"><div class="mm-nx">'+(last?(m.link?'<a class="lnk">'+m.link+'</a>':''):'Up next <b>· '+MOM[queue[i+1]].k+'</b>')+'</div><button class="btn-ghost" data-next>'+(last?'Done':'Next')+' <kbd>Enter</kbd></button></div></div>';
}
function renderMilestone(){
var v=QUEUES[q.get('v')]?q.get('v'):'signing',queue=QUEUES[v],idx=0;
var r=boot(office('win',0)+'<div class="mm-scrim" id="mms"></div>');
r.classList.add('mm-in');
function paint(){document.getElementById('mms').innerHTML=modal(queue,idx);}
paint();
r.addEventListener('click',function(ev){
var b=ev.target.closest('[data-next],.mm-x');if(!b)return;
if(b.matches('[data-next]')&&idx<queue.length-1){var mm=r.querySelector('.mm');mm.classList.add('q-out');setTimeout(function(){idx++;paint();r.querySelector('.mm').classList.add('q-in');},180);}
else{var s=document.getElementById('mms');s.style.transition='opacity 180ms';s.style.opacity='0';setTimeout(function(){s.style.display='none';},180);}
});
}
/* ── SEASON PEAK ── */
function confetti(){var h='',seed=7;function rnd(){seed=(seed*9301+49297)%233280;return seed/233280;}
for(var i=0;i<60;i++){var c=i%3===0?'w':i%5===0?'d':'g';h+='<i class="'+c+'" style="left:'+(rnd()*100).toFixed(1)+'%;--d:'+Math.round(rnd()*900)+'ms;--x:'+Math.round((rnd()-.5)*160)+'px;--r:'+Math.round(360+rnd()*540)+'deg;transform:rotate('+Math.round(rnd()*180)+'deg)"></i>';}
return '<div class="cf" aria-hidden="true">'+h+'</div>';}
function title(){
return '<section class="pk" role="dialog" aria-modal="true" aria-labelledby="pk-t"><img class="pk-art" src="../assets/lawrence_banner_primary.jpg" alt="">'+confetti()+'<div class="pk-k">Season 2 · National Tournament</div><h1 class="pk-t" id="pk-t">National Champions</h1><div class="pk-rule"></div><div class="pk-team"'+I(0)+'>Lawrence Eagles</div><div class="pk-score"'+I(1)+'><span><b>72</b> Lawrence</span><i>·</i><span class="l">Harbor City <b>66</b></span></div><div class="pk-meds"'+I(2)+'><div class="tro"><span class="med gold">C</span><div><b>Conference A2</b><span>Week 26</span></div></div><div class="tro"><span class="med gold">R</span><div><b>Region B</b><span>Week 30</span></div></div><div class="tro"><span class="med gold lg" style="--ms:64px">N</span><div><b>National</b><span>Week 34</span></div></div></div><div class="pk-f"><p>Added to your <em>Trophy Case</em>. Your season review is next.</p><div class="mq"><i class="on"></i><i></i><span>1 of 2</span></div><button class="btn-ghost lg">Continue</button></div></section>';
}
function review(){
var bp=[['Devin Park','PG · JR','All-American 1st team',[['18.9','PPG'],['6.1','APG'],['4.4','RPG']]],['Isaiah Monroe','SF · SO','All-American 3rd team',[['15.2','PPG'],['7.0','RPG'],['1.3','SPG']]],['Silas Kerr','C · SR','',[['11.8','PPG'],['9.6','RPG'],['2.1','BPG']]]];
return '<section class="rv" role="dialog" aria-modal="true" aria-labelledby="rv-t"><div class="rv-h"'+I(0)+'><span class="logo" style="--tc:#8C1D40">L</span><div><small>Season 2 in review</small><h1 id="rv-t">Lawrence Eagles</h1></div><div class="mq"><i></i><i class="on"></i><span>2 of 2</span></div></div>'+
'<div class="rv-top"'+I(1)+'><div class="rv-rec"><b>31–5</b><span>Record</span></div><div class="rv-fin"><div><b>#1</b><span>National</span></div><div><b>1st</b><span>Conference A2</span></div><div><b>1 seed</b><span>Region B</span></div></div><div class="rv-t"><div class="tro"><span class="med gold" style="--j:0">N</span><div><b>National Champions</b></div></div><div class="tro"><span class="med gold" style="--j:1">R</span><div><b>Region B Champions</b></div></div><div class="tro"><span class="med gold" style="--j:2">C</span><div><b>Conference A2 Champions</b></div></div></div></div>'+
'<div class="rv-cols"'+I(2)+'><div class="sec"><div class="sec-h"><h3>Best Players</h3><span>Season lines</span></div>'+bp.map(function(p){return '<div class="bp"><span class="portrait"><img src="'+P+'" alt=""></span><div class="bp-n"><a class="nm">'+p[0]+'</a><span>'+p[1]+(p[2]?' <span class="tg">'+p[2]+'</span>':'')+'</span><div class="bp-l">'+p[3].map(function(s){return '<div><b>'+s[0]+'</b><i>'+s[1]+'</i></div>';}).join('')+'</div></div></div>';}).join('')+'</div>'+
'<div class="sec"><div class="sec-h"><h3>Awards</h3><span>All-American teams</span></div><div class="aw"><div><b>Devin Park</b><span>PG · 18.9 PPG</span></div><span class="tg">1st team</span></div><div class="aw"><div><b>Isaiah Monroe</b><span>SF · 15.2 PPG</span></div><span class="tg">3rd team</span></div></div>'+
'<div class="sec"><div class="sec-h"><h3>Class Signed</h3><span>5 recruits</span></div><div class="rc-l" style="border-top:0">'+REC.map(function(r){return '<div class="rc"><span class="av">'+initials(r[0])+'</span><div class="rc-n"><b>'+r[0]+'</b><span>'+r[1]+'</span></div>'+rt(r[2],r[3])+'</div>';}).join('')+'</div></div></div>'+
'<div class="rv-f"'+I(3)+'><p>Saved to your <em>Trophy Case</em>. Open it any time from Home Base.</p><button class="btn-ghost lg">Continue</button></div></section>';
}
function renderPeak(){
var v=q.get('v')==='review'?'review':'title';
var r=boot(office('win',0)+(v==='review'?review():title()));
r.classList.add(v==='review'?'rv-in':'pk-in');
}
function renderOffice(){
var k=WK[q.get('s')]?q.get('s'):'win',still=q.has('still');
var r=boot(office(k,!still));
if(!still&&WK[k].won&&!q.has('rm'))countUp(r);
}
window.CH7M={renderOffice:renderOffice,renderMilestone:renderMilestone,renderPeak:renderPeak};
})();
