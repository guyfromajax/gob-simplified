/* Ch7 preview helpers. Not product code. */
(function(){
var q=new URLSearchParams(location.search);
if(q.has('embed'))document.documentElement.classList.add('embed');
var d=q.get('d')==='1920'?'1920':'1280';
function root(){var r=document.getElementById('root');r.classList.add('gob-'+d);if(q.has('rm'))r.classList.add('rm');return r;}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function rtc(l){var c=(l||'')[0];return c==='A'?'t-blue':c==='B'?'t-green':c==='C'?'t-yellow':'t-red';}
function rt(cur,pot){return '<span class="rtl"><b class="'+rtc(cur)+'">'+cur+'</b>'+(pot?'<i>→</i><b class="pot '+rtc(pot)+'">'+pot+'</b>':'')+'</span>';}
function adc(v){return v>=9?'t-blue':v>=7?'t-green':v>=5?'t-yellow':'t-red';}
function ad(v){return '<span class="ad '+adc(v)+'">'+v+'</span>';}
var A='../assets/';
var TEAMS={
lawrence:{name:'Lawrence Eagles',short:'Lawrence',tc:'#8C1D40',art:A+'lawrence_banner_primary.jpg',l:'L'},
chapel:{name:'Chapel Hill Sky',short:'Chapel Hill',tc:'#2B4C9B',art:A+'chapel_hill_banner_primary.jpg',l:'C'},
grizzly:{name:'Grizzly Academy',short:'Grizzly Academy',tc:'#23324F',art:A+'grizzly_academy_banner_primary.jpg',l:'G'}
};
var PORT=A+'portrait-placeholder.png';
window.CH7={q:q,d:d,root:root,esc:esc,rt:rt,ad:ad,TEAMS:TEAMS,PORT:PORT};
})();
