/* GOB — sim broadcast shared parts: data + piece renderers (board rows, worm, team panel,
   scoreboard, control cluster). Extracted from Mockup 1 so mockups share one source. */
const GREEN='#34EC27',BLUE='#4A90D9',ORANGE='#F79420',RED='#ff6d6d',GOLD='#FFD700';
const POSC={PG:'#4A90D9',SG:'#7B5EA7',SF:'#3A8C4A',PF:'#C0392B',C:'#D4A017'};
const RTC=r=>r>=81?BLUE:r>=61?GREEN:r>=41?GOLD:RED;
const SIL='<svg viewBox="0 0 100 100"><circle cx="50" cy="34" r="19" fill="rgba(255,255,255,0.14)"/><path d="M12 100c0-22 17-36 38-36s38 14 38 36" fill="rgba(255,255,255,0.14)"/></svg>';
const FLAME='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c1 3-1 4.5-2.5 6.5C8 10.7 7 12.4 7 14.5 7 18 9.2 21 12 21s5-3 5-6.5c0-2.4-1.3-4-2.4-5.6.2 1.6-.4 2.7-1.3 3.3.5-2.6-.9-6.4-1.3-10.2z"/></svg>';
const SNOW='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1M12 5.5l2 2M12 5.5l-2 2M12 18.5l2-2M12 18.5l-2-2M5.5 12l2 2M5.5 12l2-2M18.5 12l-2 2M18.5 12l-2-2"/></svg>';

const T={away:{abbr:'AA',name:'Ann Arbor',color:'#9E1B32',rank:18,rec:'15–8'},
         home:{abbr:'FV',name:'Fairview',color:'#2E9E5B',rank:11,rec:'19–5'}};
const SCORE={away:54,home:60,clock:'6:12',quarter:'3RD',shot:18,atol:3,htol:4,afoul:7,hfoul:11};
const AWAY=[
 {pos:'PG',name:'M. Whitney',jersey:38,rt:78,pts:12,reb:3,ast:7,def:46,fouls:3},
 {pos:'SG',name:'E. Terrell',jersey:13,rt:54,pts:9,reb:2,ast:3,def:44,fouls:2},
 {pos:'SF',name:'C. Conway',jersey:53,rt:84,pts:18,reb:7,ast:2,def:58,fouls:2,hot:true},
 {pos:'PF',name:"A. O'Brien",jersey:42,rt:89,pts:16,reb:11,ast:1,def:64,fouls:2},
 {pos:'C',name:'L. Gordon',jersey:66,rt:37,pts:6,reb:8,ast:0,def:52,fouls:4}];
const HOME=[
 {pos:'PG',name:'D. Reyes',jersey:4,rt:86,pts:14,reb:4,ast:9,def:57,fouls:1},
 {pos:'SG',name:'J. Pratt',jersey:22,rt:33,pts:5,reb:2,ast:2,def:41,fouls:2,cold:true},
 {pos:'SF',name:'I. Frank',jersey:31,rt:92,pts:22,reb:6,ast:4,def:66,fouls:2,spot:true},
 {pos:'PF',name:'T. Wilson',jersey:45,rt:59,pts:8,reb:9,ast:1,def:61,fouls:4},
 {pos:'C',name:'M. Soto',jersey:55,rt:73,pts:9,reb:7,ast:1,def:55,fouls:3,sub:true}];
const BENCH={away:[],
             home:[{name:'R. Ellis',pts:6,reb:3,out:true}]};
const WORM=[0,2,4,1,-2,-3,-1,2,5,3,6,4,2,5,7,4,1,3,6,8,5,3,6,9,7,4,6,8,6];
// team stats: [label, awayVal, homeVal, kind, betterIsLow]
const TEAMSTATS=[
 ['REBOUNDS',31,27,'tug',false],
 ['TURNOVERS',9,14,'tug',true],
 ['FAST BREAK',6,17,'tug',false],
 ['PTS IN PAINT',18,26,'tug',false],
 ['FG%','43.1','47.6','rate',false],
 ['3PM',5,8,'rate',false],
 ['TEAM FOULS',7,11,'tug',true]];


/* ---------- pieces ---------- */
function bar(label,v,max,pct){
  const fill=Math.min(v/max,1)*100, maxed=pct?v>=80:v>=max;
  const color=maxed?BLUE:GREEN, val=pct?v+'%':v;
  return `<div class="barrow"><span class="bl">${label}</span><div class="track"><div class="fill${maxed?' maxed':''}" style="width:${fill}%;background:${color};color:${color}"></div></div><span class="bv">${val}</span></div>`;
}
function pips(f,out){
  let s='';
  for(let i=0;i<5;i++){const c=out?RED:(f>=4?GOLD:'rgba(255,255,255,.7)');s+=`<span class="pip" style="background:${i<f?c:'rgba(255,255,255,.14)'}"></span>`}
  return `<span class="pips">${s}</span>`;
}
function row(p,tc){
  const st=[];
  if(p.hot)st.push(`<span class="mo flame" style="color:${ORANGE}">${FLAME}</span>`);
  if(p.cold)st.push(`<span class="mo" style="color:${BLUE}">${SNOW}</span>`);
  st.push(pips(p.fouls,p.out));
  if(p.out)st.push('<span class="tag-out">FOULED OUT</span>');
  else if(p.fouls>=4)st.push('<span class="tag-ft">FOUL TROUBLE</span>');
  return `<div class="prow${p.spot?' spot':''}${p.out?' isout':''}">
    <div class="head" style="border-color:${p.out?RED:tc}"><span class="rtb" style="background:${RTC(p.rt)}">${p.rt}</span><div class="sil">${SIL}</div></div>
    <div class="pbody">
      <div class="pname"><span class="pos" style="color:${POSC[p.pos]}">${p.pos}</span><span class="nm">${p.name}</span><span class="jn">#${p.jersey}</span>${p.spot?'<span class="spotmark">◆ TOP</span>':''}${p.sub?'<span class="tag-in">IN</span>':''}</div>
      <div class="status">${st.join('')}</div>
      <div class="bars">${bar('PTS',p.pts,20)}${bar('REB',p.reb,10)}${bar('AST',p.ast,10)}${bar('DEF',p.def,100,true)}</div>
    </div></div>`;
}
function board(list,side){
  const t=T[side];
  const head=`<div class="bhead"><span class="dot" style="background:${t.color}"></span><span>${t.name} · ${side}</span></div>`;
  return head+list.map(p=>row(p,t.color)).join('');
}
function worm(w,h,opts){
  // Fixed time domain: x is game progress, not sample index. The dot travels L→R and the
  // unplayed region stays as structure (zero line + quarter ticks) so shape stays comparable.
  const o=opts||{}, total=o.total||48, pad=6, mid=h/2, n=WORM.length;
  const maxAbs=o.clamp||Math.max(6,...WORM.map(Math.abs));
  const x=i=>pad+i*(w-pad*2)/(total-1);
  const y=m=>Math.max(pad,Math.min(h-pad,mid-(m/maxAbs)*(mid-pad)));
  let line='',area=`M ${x(0)} ${mid} `;
  WORM.forEach((m,i)=>{line+=(i?'L':'M')+` ${x(i).toFixed(1)} ${y(m).toFixed(1)} `;area+=`L ${x(i).toFixed(1)} ${y(m).toFixed(1)} `});
  area+=`L ${x(n-1)} ${mid} Z`;
  const cur=WORM[n-1], cx=x(n-1);
  const ticks=[.25,.5,.75].map(f=>`<line x1="${(pad+f*(w-pad*2)).toFixed(1)}" y1="2" x2="${(pad+f*(w-pad*2)).toFixed(1)}" y2="${h-2}" stroke="rgba(255,255,255,${f===.5?'.085':'.05'})" stroke-width="1"/>`).join('');
  const wall=o.wall?`<line x1="${x(total-1).toFixed(1)}" y1="0" x2="${x(total-1).toFixed(1)}" y2="${h}" stroke="rgba(255,255,255,.34)" stroke-width="1.5"/>`:'';
  return `<svg class="wormsvg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs>
      <linearGradient id="wgu" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${T.home.color}" stop-opacity=".45"/><stop offset="1" stop-color="${T.home.color}" stop-opacity="0"/></linearGradient>
      <linearGradient id="wgd" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${T.away.color}" stop-opacity=".45"/><stop offset="1" stop-color="${T.away.color}" stop-opacity="0"/></linearGradient>
      <clipPath id="clipu"><rect x="0" y="0" width="${w}" height="${mid}"/></clipPath>
      <clipPath id="clipd"><rect x="0" y="${mid}" width="${w}" height="${mid}"/></clipPath>
    </defs>
    ${ticks}${wall}
    <line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="rgba(255,255,255,.16)" stroke-width="1" stroke-dasharray="3 4"/>
    <path d="${area}" fill="url(#wgu)" clip-path="url(#clipu)"/>
    <path d="${area}" fill="url(#wgd)" clip-path="url(#clipd)"/>
    <path d="${line}" fill="none" stroke="${T.home.color}" stroke-width="2.2" stroke-linejoin="round" clip-path="url(#clipu)"/>
    <path d="${line}" fill="none" stroke="${T.away.color}" stroke-width="2.2" stroke-linejoin="round" clip-path="url(#clipd)"/>
    <line x1="${cx.toFixed(1)}" y1="2" x2="${cx.toFixed(1)}" y2="${h-2}" stroke="rgba(255,255,255,.14)" stroke-width="1"/>
    <circle class="wormdot" cx="${cx.toFixed(1)}" cy="${y(cur).toFixed(1)}" r="3.4" fill="${cur>=0?T.home.color:T.away.color}"/>
  </svg>`;
}
function teamPanel(rows){
  const src=rows||TEAMSTATS;
  const out=src.map(([lb,a,h,kind,low])=>{
    const na=parseFloat(a),nh=parseFloat(h);
    const homeBetter=low?nh<na:nh>na, tie=na===nh;
    if(kind==='rate') return `<div class="tsr"><span class="lb">${lb}</span><span class="va${!tie&&!homeBetter?' lead':''}">${a}</span><div class="pivot"></div><span class="vh${!tie&&homeBetter?' lead':''}">${h}</span></div>`;
    const edge=Math.abs(na-nh), denom=Math.max(na,nh,1);
    const pct=Math.min(edge/denom,1)*50;
    const col=homeBetter?T.home.color:T.away.color;
    const pull=tie?'':`<div class="pull" style="${homeBetter?'left:50%':'right:50%'};width:${pct}%;background:linear-gradient(${homeBetter?'90deg':'270deg'},${col}44,${col})"></div>`;
    return `<div class="tsr"><span class="lb">${lb}</span><span class="va${!tie&&!homeBetter?' lead':''}">${a}</span><div class="tug">${pull}</div><span class="vh${!tie&&homeBetter?' lead':''}">${h}</span></div>`;
  }).join('');
  return `<div class="tsp"><div class="tsp-head"><span class="tsp-cap">TEAM</span><span class="tsp-note">bar pulls toward better</span></div>${out}</div>`;
}
function controls(){
  return `<div class="ctl${S.ctl==='right'?' right':''}">
    <div class="ctlseg" data-rest><button data-v="worm" class="${S.rest==='worm'?'on':''}">HIGHLIGHTS</button><button data-v="team" class="${S.rest==='team'?'on':''}">TEAM STATS</button></div>
    <button class="ctlbtn">1×</button><button class="ctlbtn">▶▶</button></div>`;
}
function scoreboard(){
  return `<div class="sb-side left">
    <div class="sb-logo" style="background:linear-gradient(135deg,${T.away.color},#0b0d14)">${T.away.abbr}</div>
    <div class="sb-meta"><span class="sb-rank">#${T.away.rank}</span><span class="sb-rec">${T.away.rec}</span></div>
    <div class="sb-score">${SCORE.away}</div>
    <div class="sb-tf"><span>TOL ${SCORE.atol}</span><span>F ${SCORE.afoul}</span></div></div>
  <div class="sb-center"><div class="sb-clock">${SCORE.clock}</div><div class="sb-per"><span class="sb-q">${SCORE.quarter}</span><span class="sb-shot">${SCORE.shot}</span></div></div>
  <div class="sb-side right">
    <div class="sb-tf right"><span>TOL ${SCORE.htol}</span><span>F ${SCORE.hfoul}</span></div>
    <div class="sb-score">${SCORE.home}</div>
    <div class="sb-meta right"><span class="sb-rank">#${T.home.rank}</span><span class="sb-rec">${T.home.rec}</span></div>
    <div class="sb-logo" style="background:linear-gradient(225deg,${T.home.color},#0b0d14)">${T.home.abbr}</div></div>
  <div class="sb-edge" style="--al:${T.away.color};--hl:${T.home.color}"></div>`;
}
