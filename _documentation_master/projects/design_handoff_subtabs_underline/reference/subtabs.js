(function(){
const I={
lock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/></svg>',
chev:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 9.5L12 15l5.5-5.5"/></svg>',
search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>'};
const LT={t:'Tournament',lock:'Week 27'};
const LEAGUE=['Standings','Rankings','Leaders','Team Stats','Schedule','Practice Squad',LT];
const SCOPE={seg:['Conference','Region','National'],on:1};
const S={
team:{title:'Team',rail:1,crumb:'Chapel Hill · A2 Conference · 12 players',tabs:['Roster','Player Stats','Team Attributes','Schedule'],active:0,tools:[{seg:[['Varsity',12],['Practice Squad',3]],on:0}]},
prep:{title:'Prep',rail:2,crumb:'Week 22 · next game Saturday',tabs:['Training','Game Plan','Playbooks','Scouting Report'],active:1,tools:[]},
league:{title:'League',rail:3,crumb:'128 teams · 16 conferences · 8 regions',tabs:LEAGUE,active:0,tools:[SCOPE,{search:'Find a team'}]},
leagueStats:{title:'League',rail:3,crumb:'128 teams · 16 conferences · 8 regions',tabs:LEAGUE,active:3,tools:[SCOPE,{seg:['Per game','Totals'],on:0},{search:'Find a team'}]},
recruiting:{title:'Recruiting',rail:4,crumb:'Class of 2027 · 3 visits this week',tabs:['Pool','Leans','Visits'],active:0,tools:[{seg:['All','Region','Watchlist'],on:0},{search:'Find a recruit'}]},
news:{title:'News',rail:5,crumb:'',tabs:['News','Awards'],active:0,tools:[]}};
const lbl=t=>typeof t==='string'?t:t.t;
function tabsHTML(sec){
return '<div class="tabs" role="tablist" aria-label="'+sec.title+' sections">'+sec.tabs.map((t,i)=>{
const sel=i===sec.active,lk=typeof t==='object'&&t.lock;
return '<a class="tb" role="tab" data-i="'+i+'" aria-selected="'+sel+'" tabindex="'+(sel?0:-1)+'"'+(lk?' aria-disabled="true" data-lock="'+t.lock+'"':'')+'>'+lbl(t)+(lk?I.lock+'<span class="ltip" role="tooltip"><b>Locked until '+t.lock+'</b><span>Tournament opens when the regular season ends.</span></span>':'')+'</a>';
}).join('')+'<span class="more-w"><button class="tb more" aria-haspopup="menu" aria-expanded="false" tabindex="-1">More'+I.chev+'</button><div class="mmenu" role="menu"></div></span><i class="ink" aria-hidden="true"></i></div>';}
function toolsHTML(sec){
if(!sec.tools.length)return '';
return '<div class="pg-tools">'+sec.tools.map(t=>{
if(t.search)return '<label class="search">'+I.search+'<input type="text" placeholder="'+t.search+'"><kbd>/</kbd></label><button class="sbtn" aria-label="'+t.search+'">'+I.search+'</button>';
return '<div class="seg" role="radiogroup">'+t.seg.map((s,i)=>{const [n,c]=Array.isArray(s)?s:[s];return '<button class="'+(i===t.on?'on':'')+'" role="radio" aria-checked="'+(i===t.on)+'">'+n+(c!=null?'<em>'+c+'</em>':'')+'</button>';}).join('')+'</div>';
}).join('')+'</div>';}
function head(dir,sec,o={}){
const st=o.static?' st':'';
if(dir==='C')return '<div class="pg-head'+st+'"><div class="nav-row"><h1 class="h1c">'+sec.title+'</h1><span class="vr"></span>'+tabsHTML(sec)+toolsHTML(sec)+'</div></div>';
return '<div class="pg-head'+st+'"><div class="pg-title"><h1>'+sec.title+'</h1>'+(sec.crumb?'<span class="crumb">'+sec.crumb+'</span>':'')+'</div><div class="nav-row">'+tabsHTML(sec)+toolsHTML(sec)+'</div></div>';}
function row(dir,sec){return '<div class="nav-row">'+tabsHTML(sec)+toolsHTML(sec)+'</div>';}

function placeInk(r){
const ink=r.querySelector('.ink'),a=r.querySelector('.tb[aria-selected="true"]');if(!ink||!a)return;
ink.style.width=a.offsetWidth+'px';ink.style.transform='translateX('+a.offsetLeft+'px)';
if(!ink.classList.contains('ready'))requestAnimationFrame(()=>requestAnimationFrame(()=>ink.classList.add('ready')));}
function fit(r){
const tbs=[...r.querySelectorAll('.tabs>.tb')],mw=r.querySelector('.more-w'),se=r.querySelector('.search'),sb=r.querySelector('.sbtn'),menu=r.querySelector('.mmenu');
tbs.forEach(t=>t.classList.remove('ovf'));mw.classList.remove('show');
const over=()=>r.scrollWidth>r.clientWidth+1;
if(se){se.classList.remove('col');sb.classList.remove('show');if(r.dataset.searchOpen!=='1'&&over()){se.classList.add('col');sb.classList.add('show');}}
if(over()){mw.classList.add('show');for(let i=tbs.length-1;i>=0&&over();i--){if(tbs[i].getAttribute('aria-selected')==='true')continue;tbs[i].classList.add('ovf');}}
menu.innerHTML=tbs.filter(t=>t.classList.contains('ovf')).map(t=>{const lk=t.dataset.lock;return '<a class="mi" role="menuitem" tabindex="-1" data-i="'+t.dataset.i+'"'+(lk?' aria-disabled="true"':'')+'>'+t.childNodes[0].textContent+(lk?I.lock+'<em>Unlocks '+lk+'</em>':'')+'</a>';}).join('');
placeInk(r);}
function select(r,t){
if(!t||t.dataset.lock||t.classList.contains('more'))return;
r.querySelectorAll('.tabs>.tb').forEach(x=>{const on=x===t;x.setAttribute('aria-selected',on&&!x.classList.contains('more'));x.tabIndex=on?0:-1;});
fit(r);}
function closeMenu(r,focus){const m=r.querySelector('.mmenu'),b=r.querySelector('.more');m.classList.remove('open');b.setAttribute('aria-expanded','false');if(focus)b.focus();}
function openMenu(r){const m=r.querySelector('.mmenu'),b=r.querySelector('.more');m.classList.add('open');b.setAttribute('aria-expanded','true');const f=m.querySelector('.mi');f&&f.focus();}
function wire(r){
const tabs=r.querySelector('.tabs');
tabs.addEventListener('click',e=>{const t=e.target.closest('.tb');if(!t)return;if(t.classList.contains('more')){r.querySelector('.mmenu').classList.contains('open')?closeMenu(r):openMenu(r);return;}select(r,t);});
tabs.addEventListener('keydown',e=>{
const mi=e.target.closest('.mi');
if(mi){const items=[...r.querySelectorAll('.mi')],k=items.indexOf(mi);
if(e.key==='ArrowDown'){e.preventDefault();items[(k+1)%items.length].focus();}
else if(e.key==='ArrowUp'){e.preventDefault();items[(k-1+items.length)%items.length].focus();}
else if(e.key==='Escape'){e.preventDefault();closeMenu(r,true);}
else if(e.key==='Enter'||e.key===' '){e.preventDefault();if(!mi.hasAttribute('aria-disabled')){const t=r.querySelector('.tabs>.tb[data-i="'+mi.dataset.i+'"]');closeMenu(r);select(r,t);t.focus();}}
return;}
const vis=[...r.querySelectorAll('.tabs>.tb:not(.ovf)')].filter(t=>t.offsetParent!==null),k=vis.indexOf(e.target);if(k<0)return;
let n=null;
if(e.key==='ArrowRight')n=vis[(k+1)%vis.length];else if(e.key==='ArrowLeft')n=vis[(k-1+vis.length)%vis.length];else if(e.key==='Home')n=vis[0];else if(e.key==='End')n=vis[vis.length-1];
else if(e.target.classList.contains('more')&&(e.key==='Enter'||e.key===' '||e.key==='ArrowDown')){e.preventDefault();openMenu(r);return;}
if(n){e.preventDefault();vis.forEach(t=>t.tabIndex=-1);n.tabIndex=0;n.focus();if(!n.dataset.lock&&!n.classList.contains('more'))select(r,n),n.tabIndex=0;}});
tabs.addEventListener('click',e=>{const mi=e.target.closest('.mi');if(!mi||mi.hasAttribute('aria-disabled'))return;const t=r.querySelector('.tabs>.tb[data-i="'+mi.dataset.i+'"]');closeMenu(r);select(r,t);});
document.addEventListener('mousedown',e=>{if(!r.contains(e.target))closeMenu(r);});
r.querySelectorAll('.seg').forEach(g=>g.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;g.querySelectorAll('button').forEach(x=>{x.classList.toggle('on',x===b);x.setAttribute('aria-checked',x===b);});fit(r);}));
const sb=r.querySelector('.sbtn'),inp=r.querySelector('.search input');
if(sb){sb.addEventListener('click',()=>{r.dataset.searchOpen='1';fit(r);inp.focus();});
inp.addEventListener('blur',()=>{if(!inp.value&&r.dataset.searchOpen==='1'){r.dataset.searchOpen='0';fit(r);}});}
}
function applyState(r,s){
if(!s)return;
const by=n=>[...r.querySelectorAll('.tabs>.tb')].find(t=>t.childNodes[0].textContent===n);
const on=(n,...c)=>{const t=n&&by(n);if(t)t.classList.add(...c);};
on(s.hover,'is-hover');on(s.focus,'is-focus');on(s.tip,'is-hover','is-tip');
if(s.menu){const m=r.querySelector('.mmenu'),b=r.querySelector('.more');m.classList.add('open');b.setAttribute('aria-expanded','true');const it=s.menuFocus!=null&&m.querySelectorAll('.mi')[s.menuFocus];if(it)it.classList.add('is-focus');}
}
window.SX={S,head,row,fit,wire,applyState,placeInk,LT};
})();
