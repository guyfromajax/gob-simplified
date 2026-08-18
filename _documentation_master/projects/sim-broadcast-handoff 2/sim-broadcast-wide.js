/* GOB — mockup 4 pieces: compressed wide worm, compact lineup rows, callout engine.
   Depends on sim-broadcast-parts.js for T / AWAY / HOME / SIL / FLAME / SNOW / POSC / RTC. */
(function(){
const KNEE=10, BEYOND=.20;   // full scale inside a 10-point game, 20% of it past that
/* Nonlinear, FIXED y scale — the same margin plots at the same height all game. Deliberately not
   auto-fit: a scale that changes under you makes shape incomparable across the broadcast. */
function compress(m,knee,beyond){
  const a=Math.abs(m), c=Math.min(a,knee)+Math.max(0,a-knee)*beyond;
  return m<0?-c:c;
}
function wormWide(series,w,h,o){
  o=o||{};
  const knee=o.knee||KNEE, beyond=o.beyond==null?BEYOND:o.beyond, total=o.total||48;
  const padX=4, padY=10, mid=h/2;
  const domain=compress(o.domain||45,knee,beyond);
  const x=i=>padX+i*(w-padX*2)/(total-1);
  const y=m=>{
    const v=compress(m,knee,beyond)/domain;
    return Math.max(padY,Math.min(h-padY,mid-v*(mid-padY)));
  };
  const n=series.length, cur=series[n-1];
  let line='',area=`M ${x(0)} ${mid} `;
  series.forEach((m,i)=>{const px=x(i).toFixed(1),py=y(m).toFixed(1);line+=(i?'L':'M')+` ${px} ${py} `;area+=`L ${px} ${py} `});
  area+=`L ${x(n-1)} ${mid} Z`;
  // knee guides: where the scale changes slope, drawn faintly so the compression is disclosed
  const kneeY=[y(knee),y(-knee)].map(v=>`<line x1="0" y1="${v.toFixed(1)}" x2="${w}" y2="${v.toFixed(1)}" stroke="rgba(255,255,255,.055)" stroke-width="1" stroke-dasharray="2 6"/>`).join('');
  const ticks=[.25,.5,.75].map(f=>{const tx=(padX+f*(w-padX*2)).toFixed(1);
    return `<line x1="${tx}" y1="0" x2="${tx}" y2="${h}" stroke="rgba(255,255,255,${f===.5?'.08':'.045'})" stroke-width="1"/>`}).join('');
  const cx=x(n-1), cy=y(cur);
  const wall=`<line x1="${x(total-1).toFixed(1)}" y1="0" x2="${x(total-1).toFixed(1)}" y2="${h}" stroke="rgba(255,255,255,${o.wall?'.3':'.12'})" stroke-width="${o.wall?1.5:1}"/>`;
  const svg=`<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <defs>
      <linearGradient id="w4u" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${T.home.color}" stop-opacity=".42"/><stop offset="1" stop-color="${T.home.color}" stop-opacity="0"/></linearGradient>
      <linearGradient id="w4d" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${T.away.color}" stop-opacity=".42"/><stop offset="1" stop-color="${T.away.color}" stop-opacity="0"/></linearGradient>
      <clipPath id="w4cu"><rect x="0" y="0" width="${w}" height="${mid}"/></clipPath>
      <clipPath id="w4cd"><rect x="0" y="${mid}" width="${w}" height="${mid}"/></clipPath>
    </defs>
    ${ticks}${kneeY}${wall}
    <line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="rgba(255,255,255,.16)" stroke-width="1" stroke-dasharray="3 4"/>
    <path d="${area}" fill="url(#w4u)" clip-path="url(#w4cu)"/>
    <path d="${area}" fill="url(#w4d)" clip-path="url(#w4cd)"/>
    <path d="${line}" fill="none" stroke="${T.home.color}" stroke-width="2.4" stroke-linejoin="round" clip-path="url(#w4cu)"/>
    <path d="${line}" fill="none" stroke="${T.away.color}" stroke-width="2.4" stroke-linejoin="round" clip-path="url(#w4cd)"/>
    <line x1="${cx.toFixed(1)}" y1="0" x2="${cx.toFixed(1)}" y2="${h}" stroke="rgba(255,255,255,.13)" stroke-width="1"/>
    <circle class="wormdot4" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="4" fill="${cur>=0?T.home.color:T.away.color}"/>
  </svg>`;
  const prev=n>1?y(series[n-2]):cy;
  return {svg,cx,cy,rising:cy<prev};
}

/* ---- compact lineup row: portrait + identity + four stat cells ---- */
function cell(v,max,pct){
  const maxed=pct?v>=80:v>=max, col=maxed?'#4A90D9':'#34EC27';
  return `<div class="c4"><span class="v">${pct?v+'%':v}</span><div class="t"><div class="f" style="width:${Math.min(v/max,1)*100}%;background:${col}"></div></div></div>`;
}
function row4(p,tc){
  const st=[];
  if(p.hot)st.push(`<span class="mo flame" style="color:#F79420">${FLAME}</span>`);
  if(p.cold)st.push(`<span class="mo" style="color:#4A90D9">${SNOW}</span>`);
  let pips='';
  for(let i=0;i<5;i++){const c=p.out?'#ff6d6d':(p.fouls>=4?'#FFD700':'rgba(255,255,255,.7)');
    pips+=`<span class="pip" style="background:${i<p.fouls?c:'rgba(255,255,255,.14)'}"></span>`}
  st.push(`<span class="pips">${pips}</span>`);
  if(p.out)st.push('<span class="tag4" style="background:#ff6d6d;color:#2a0606">OUT</span>');
  else if(p.fouls>=4)st.push('<span class="tag4" style="color:#FFD700;box-shadow:inset 0 0 0 1px rgba(255,215,0,.4)">FOUL TROUBLE</span>');
  if(p.sub)st.push('<span class="tag4" style="background:#34EC27;color:#06210a">IN</span>');
  const cls='r4'+(p.spot?' spot':'')+(p.out?' isout':'')+(!p.out&&p.fouls>=4?' ft':'');
  return `<div class="${cls}">
    <div class="h4" style="border-color:${p.out?'#ff6d6d':tc}"><span class="rt4" style="background:${RTC(p.rt)}">${p.rt}</span>${SIL}</div>
    <div class="id4">
      <div class="n4"><span class="pos" style="color:${POSC[p.pos]}">${p.pos}</span><span class="nm">${p.name}</span><span class="jn">#${p.jersey}</span></div>
      <div class="s4">${st.join('')}</div>
    </div>
    ${cell(p.pts,20)}${cell(p.reb,10)}${cell(p.ast,10)}${cell(p.def,100,true)}</div>`;
}
function lineupPane(list,side){
  const t=T[side];
  return `<div class="pane">
    <div class="pane-head"><span class="dot" style="background:${t.color}"></span><span>${t.name}</span><span class="sp"></span>
      <span class="cols"><span>PTS</span><span>REB</span><span>AST</span><span>DEF</span></span></div>
    <div class="lineup">${list.map(p=>row4(p,t.color)).join('')}</div></div>`;
}
function statsPane(rows){
  const out=rows.map(([lb,a,h,kind,low,pointLow])=>{
    const na=parseFloat(a),nh=parseFloat(h),homeBetter=low?nh<na:nh>na,tie=na===nh;
    const pl=pointLow==null?low:pointLow, barHome=pl?nh<na:nh>na;
    const pct=Math.min(Math.abs(na-nh)/Math.max(na,nh,1),1)*50, col=barHome?T.home.color:T.away.color;
    const pull=tie?'':`<div class="pull" style="${barHome?'left:50%':'right:50%'};width:${pct}%;background:linear-gradient(${barHome?'90deg':'270deg'},${col}44,${col})"></div>`;
    return `<div class="tsr4"><span class="lb">${lb}</span><span class="va${!tie&&!homeBetter?' lead':''}">${a}</span><div class="tug4">${pull}</div><span class="vh${!tie&&homeBetter?' lead':''}">${h}</span></div>`;
  }).join('');
  return `<div class="pane"><div class="pane-head"><span>Team</span><span class="sp"></span><span style="font-size:8px;color:rgba(255,255,255,.25)">bar shows the edge</span></div><div class="tsp4">${out}</div></div>`;
}
window.Wide={compress,wormWide,row4,lineupPane,statsPane,KNEE,BEYOND};
})();
