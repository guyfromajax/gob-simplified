(function(){
'use strict';
var IMG='art/tribute/';
var HOLD=6000;
var TITLES=[['conf_rs','Conf. Regular Season'],['conf_t','Conf. Tourney'],['region','Region Tourney'],['national','National Tourney']];

var ROSTER=[
 {n:'Trent Athens',num:'07',pos:'SG',ppg:19.4,rpg:2.3,apg:2.4,def:70,gp:112,pts:2173,big:'cut-athens.png',sm:'thumb-athens.png'},
 {n:'Kent McManus',num:'12',pos:'SF',ppg:12.8,rpg:0.2,apg:1.3,def:54,gp:104,pts:1331,big:'cut-mcmanus.png',sm:'thumb-mcmanus.png'},
 {n:'CJ Castleman',num:'44',pos:'C',ppg:8.5,rpg:8.2,apg:0.6,def:54,gp:110,pts:935,big:'cut-mcmanus.png',sm:'thumb-castleman.png'},
 {n:'Clint Workman',num:'21',pos:'PG',ppg:5.8,rpg:1.5,apg:2.1,def:61,gp:98,pts:568,big:'cut-athens.png',sm:'thumb-workman.png'},
 {n:'Pete Del Fino',num:'13',pos:'PG',ppg:2.6,rpg:0.2,apg:2.5,def:62,gp:87,pts:226,big:'cut-mcmanus.png',sm:'thumb-delfino.png'},
 {n:'Marcus Whitlow',num:'05',pos:'PF',ppg:7.1,rpg:5.4,apg:0.9,def:58,gp:96,pts:682,big:'cut-mcmanus.png',sm:'thumb-castleman.png'},
 {n:'Dee Ferrante',num:'33',pos:'SG',ppg:9.6,rpg:2.0,apg:3.1,def:63,gp:101,pts:970,big:'cut-athens.png',sm:'thumb-workman.png'},
 {n:'Sam Oyelaran',num:'50',pos:'C',ppg:4.2,rpg:6.6,apg:0.4,def:66,gp:92,pts:386,big:'cut-mcmanus.png',sm:'thumb-castleman.png'},
 {n:'Rudy Kaminski',num:'08',pos:'PG',ppg:3.4,rpg:1.1,apg:4.2,def:59,gp:88,pts:299,big:'cut-athens.png',sm:'thumb-delfino.png'},
 {n:'Theo Bright',num:'15',pos:'SF',ppg:11.2,rpg:3.8,apg:1.6,def:57,gp:99,pts:1109,big:'cut-athens.png',sm:'thumb-athens.png'},
 {n:'Nate Salcedo',num:'24',pos:'SG',ppg:6.0,rpg:2.2,apg:1.9,def:60,gp:94,pts:564,big:'cut-mcmanus.png',sm:'thumb-mcmanus.png'},
 {n:'Owen Trask',num:'31',pos:'PF',ppg:5.1,rpg:4.9,apg:0.7,def:64,gp:90,pts:459,big:'cut-athens.png',sm:'thumb-workman.png'}
];
var LONGNAME='Maximilian Vandersteen-Okonkwo';
var FULL_TITLES={conf_rs:2,conf_t:1,region:1,national:1};

var opt={count:5,titles:false,longName:false,noShot:false,rm:false,season:1};
var state={i:0,phase:'slide',list:[],timer:null};
var root=document.getElementById('app');

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function nf(n){return String(n).replace(/\B(?=(\d{3})+(?!\d))/g,',');}
function one(v){return Number(v).toFixed(1);}
function initials(n){return String(n).split(/\s+/).map(function(w){return w[0];}).join('').slice(0,2).toUpperCase();}
function tlist(p){var t=p.titles||{},o=[];TITLES.forEach(function(x){var c=Number(t[x[0]]||0);if(c)o.push({label:x[1],count:c});});return o;}
function dots(p){var n=tlist(p).reduce(function(a,b){return a+b.count;},0);if(!n)return '';var s='';for(var i=0;i<n;i++)s+='<s></s>';return '<div class="lp-cti" aria-hidden="true">'+s+'</div>';}
function sizeClass(){var lp=root.querySelector('.lp');if(lp)lp.classList.toggle('narrow',(lp.clientWidth||window.innerWidth)<821);}
window.addEventListener('resize',sizeClass);
function reduced(){return opt.rm||window.matchMedia('(prefers-reduced-motion: reduce)').matches;}

function buildList(){
 var list=ROSTER.slice(0,opt.count).map(function(p){
  var q=Object.assign({},p);
  if(opt.titles)q.titles=FULL_TITLES;
  return q;
 });
 if(opt.longName&&list.length)list[0]=Object.assign({},list[0],{n:LONGNAME,num:'33',pos:'PF',ppg:16.2,rpg:9.4,apg:1.8,def:68,gp:118,pts:1911});
 return list;
}

/* ---------- markup ---------- */
function shotHtml(p,size){
 if(opt.noShot)return '<div class="lp-noshot"><b>'+esc(p.num)+'</b><small>'+esc(p.pos)+' · Senior</small></div>';
 return '<img src="'+IMG+(size==='big'?p.big:p.sm)+'" alt="" decoding="async">';
}
function slideHtml(p,i,total){
 var parts=String(p.n).split(' '),first=parts.shift(),last=parts.join(' ');
 var t=tlist(p);
 return '<div class="lp-slide in">'+
  '<div class="lp-copy">'+
   '<div class="lp-eyebrow">Class of Season '+opt.season+' · #'+esc(p.num)+' · '+esc(p.pos)+'</div>'+
   '<h2 class="lp-name'+(p.n.length>18?' long':'')+'"><span>'+esc(first)+'</span><em>'+esc(last)+'</em></h2>'+
   '<div class="lp-hr"></div>'+
   '<div class="lp-stats"><u><em>ppg</em><b>'+one(p.ppg)+'</b></u><u><em>rpg</em><b>'+one(p.rpg)+'</b></u><u><em>apg</em><b>'+one(p.apg)+'</b></u><u><em>def%</em><b>'+p.def+'</b></u></div>'+
   '<div class="lp-career">'+p.gp+' games · '+nf(p.pts)+' career points · four seasons in a Knights uniform</div>'+
   (t.length?'<div class="lp-titles">'+t.map(function(x){return '<span><s></s>'+esc(x.count>1?x.count+'× '+x.label:x.label)+'</span>';}).join('')+'</div>':'')+
  '</div>'+
  '<div class="lp-shot">'+(opt.noShot?'':'<div class="lp-shot-num" aria-hidden="true">'+esc(p.num)+'</div>')+shotHtml(p,'big')+'</div>'+
 '</div>';
}
function cardHtml(p,i,single){
 return '<div class="lp-card" style="--d:'+(i*55)+'ms" data-num="'+esc(p.num)+'">'+
  '<div class="lp-shotbox"><div class="lp-cnum" aria-hidden="true">'+esc(p.num)+'</div>'+
   (opt.noShot?'<div class="lp-cinit">'+esc(initials(p.n))+'</div>':shotHtml(p,single?'big':'sm'))+'</div>'+
  '<div class="lp-cnm">'+esc(p.n)+'</div>'+
  '<div class="lp-cmeta">'+esc(p.pos)+' · '+p.gp+' games</div>'+
  '<div class="lp-cst"><u><em>ppg</em><b>'+one(p.ppg)+'</b></u><u><em>rpg</em><b>'+one(p.rpg)+'</b></u><u><em>apg</em><b>'+one(p.apg)+'</b></u><u><em>def%</em><b>'+p.def+'</b></u></div>'+
  dots(p)+
 '</div>';
}
function chrome(right){
 return '<div class="lp-bar"><i></i></div>'+
  '<div class="lp-top"><div class="lp-brand"><small>Season '+opt.season+'</small><b>Senior Tribute</b></div>'+
  '<div class="lp-count">'+right+'</div></div>';
}

/* ---------- render ---------- */
function renderShell(){
 root.innerHTML='<div class="lp" role="dialog" aria-modal="true" aria-label="Senior Tribute">'+chrome('')+'<div class="lp-stage"></div></div>';
 return root.querySelector('.lp');
}
function renderSlide(){
 var list=state.list,p=list[state.i];
 var lp=root.querySelector('.lp'),stage=lp&&lp.querySelector('.lp-stage');
 if(!lp||!stage){lp=renderShell();stage=lp.querySelector('.lp-stage');}
 lp.className='lp';
 lp.querySelector('.lp-count').textContent=(state.i+1)+' of '+list.length;
 var prev=stage.querySelector('.lp-slide');
 stage.insertAdjacentHTML('beforeend',slideHtml(p,state.i,list.length));
 if(prev){
  if(reduced())prev.remove();
  else{prev.classList.remove('in');prev.classList.add('out');setTimeout(function(){prev.remove();},320);}
 }
 var bar=lp.querySelector('.lp-bar i');
 if(reduced()){bar.classList.remove('run');bar.style.setProperty('--step',(state.i+1)/list.length);}
 else{bar.classList.remove('run');void bar.offsetWidth;bar.style.setProperty('--hold',HOLD+'ms');bar.classList.add('run');}
 sizeClass();
}
function renderRes(flipFrom){
 var list=state.list,single=list.length===1;
 var lp=root.querySelector('.lp');
 lp.className='lp '+(single?'c-1':list.length<=6?'c-few':'c-many');
 lp.style.setProperty('--cols',String(Math.min(list.length,6)));
 lp.innerHTML=chrome('Class of Season '+opt.season)+
  '<div class="lp-res">'+
   '<div class="lp-head"><h2>Class of Season '+opt.season+'</h2><small>'+list.length+' senior'+(list.length>1?'s':'')+' · thank you</small></div>'+
   '<div class="lp-cards">'+list.map(function(p,i){return cardHtml(p,i,single);}).join('')+'</div>'+
   '<button type="button" class="lp-cta" id="lp-advance">Advance To Next Season</button>'+
  '</div>';
 lp.querySelector('.lp-bar i').style.transform='scaleX(1)';
 lp.querySelector('#lp-advance').addEventListener('click',advanceSeason);
 sizeClass();
 if(flipFrom&&!reduced())flip(flipFrom,list[list.length-1]);
}

/* last slide's portrait travels into its card */
function flip(from,player){
 var cards=root.querySelectorAll('.lp-card');
 var target=null;
 for(var i=0;i<cards.length;i++) if(cards[i].dataset.num===player.num) target=cards[i];
 target=target||cards[cards.length-1];
 var img=target&&target.querySelector('.lp-shotbox img');
 if(!img)return;
 var to=img.getBoundingClientRect();
 var clone=img.cloneNode(true);
 clone.className='lp-flip';
 clone.style.left=from.left+'px';clone.style.top=from.top+'px';
 clone.style.width=from.width+'px';clone.style.height=from.height+'px';
 document.body.appendChild(clone);
 img.style.opacity='0';
 requestAnimationFrame(function(){
  clone.style.transition='all .52s cubic-bezier(.3,.85,.25,1)';
  clone.style.left=to.left+'px';clone.style.top=to.top+'px';
  clone.style.width=to.width+'px';clone.style.height=to.height+'px';
 });
 setTimeout(function(){img.style.opacity='';clone.remove();},560);
}

/* ---------- sequence ---------- */
function stop(){if(state.timer){clearTimeout(state.timer);state.timer=null;}}
function tick(){
 stop();
 state.timer=setTimeout(function(){
  if(state.i+1>=state.list.length){
   var im=root.querySelector('.lp-slide .lp-shot img');
   var rect=im?im.getBoundingClientRect():null;
   state.phase='res';renderRes(rect);
   return;
  }
  state.i+=1;renderSlide();tick();
 },HOLD);
}
function start(){
 stop();
 state.list=buildList();state.i=0;state.phase='slide';
 renderShell();renderSlide();tick();
}
function jumpRes(){stop();state.list=buildList();state.phase='res';if(!root.querySelector('.lp'))renderShell();renderRes(null);}
function advanceSeason(){
 var b=root.querySelector('#lp-advance');
 if(b){b.disabled=true;b.textContent='Advancing…';}
 setTimeout(function(){if(b){b.disabled=false;b.textContent='Advance To Next Season';}},1400);
}

/* ---------- review dock ---------- */
var dock=document.getElementById('dock');
dock.addEventListener('click',function(e){
 var b=e.target.closest('button');if(!b)return;
 if(b.dataset.toggle!==undefined){dock.classList.toggle('hid');b.textContent=dock.classList.contains('hid')?'Review controls':'Hide';return;}
 var k=b.dataset.k,v=b.dataset.v;
 if(k==='count'){opt.count=Number(v);mark(b);start();}
 if(k==='titles'){opt.titles=v==='1';mark(b);state.phase==='res'?jumpRes():start();}
 if(k==='name'){opt.longName=v==='1';mark(b);start();}
 if(k==='shot'){opt.noShot=v==='1';mark(b);state.phase==='res'?jumpRes():start();}
 if(k==='rm'){opt.rm=v==='1';mark(b);document.documentElement.classList.toggle('rm',opt.rm);state.phase==='res'?jumpRes():start();}
 if(k==='go'){v==='res'?jumpRes():start();}
});
function mark(b){b.parentNode.querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b);});}
window.addEventListener('keydown',function(e){if(e.key==='r'||e.key==='R')start();if(e.key==='e'||e.key==='E')jumpRes();});
start();
})();
