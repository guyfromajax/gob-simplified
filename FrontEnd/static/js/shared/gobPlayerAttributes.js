/* ===========================================================
   GOB — Player Attributes lesson (tutorial sub-page)
   Category rows: each attribute shows where it Matters Most + its definition.
   Emotion & Momentum render their meters inline.
   Definitions are VERBATIM from the legacy tutorial.html — do not paraphrase.
   On load, marks the topic explored so the hub's progress/next-up light up.
   =========================================================== */
(function () {
  'use strict';
  function sfx(f) { if (window.GOB && window.GOB.playSound) window.GOB.playSound(f); }

  // wayfinding tints only (NOT data colors)
  var TYPES = {
    offense:     { label: 'Offense',       color: '#f79420', ink: '#15181f' },
    defense:     { label: 'Defense',       color: '#4a90d9', ink: '#08152b' },
    technical:   { label: 'Technical',     color: '#7b5ea7', ink: '#ffffff' },
    physical:    { label: 'Physical',      color: '#aeb8cc', ink: '#10141c' },
    intangibles: { label: 'Intangibles',   color: '#d4a017', ink: '#1a1500' },
    state:       { label: 'In-Game State', color: '#8893a8', ink: '#0d1117' }
  };

  var ATTRS = [
    { code:'SC', name:'Scoring',        type:'offense',     zone:'At the rim & in traffic',
      desc:"Simply put, this is a player's ability to put the ball in the hoop. A high SC score indicates a player's ability to utilize post moves and adjust his shot to score in high-traffic areas. The closer the shot is to the basket, the more relevant this trait will be." },
    { code:'SH', name:'Shooting',       type:'offense',     zone:'Beyond the arc',
      desc:"You guessed it! This is a player's ability to shoot the rock. It's most important on outside shots — particularly 3-pointers. The further away a player's shot is from the basket, the more relevant this trait will be." },
    { code:'ID', name:'Inside Defense', type:'defense',     zone:'At the rim',
      desc:"The ability to defend near and around the basket. The closer the opponent's shot is to the hoop, the more relevant this trait is. Taller players with high ID scores will establish themselves as \"rim protectors\" and block more shots." },
    { code:'OD', name:'Outside Defense',type:'defense',     zone:'On the perimeter',
      desc:"This trait represents a player's ability to guard the perimeter. Outside shots and drives to the hoop are better guarded by players with a high OD score. Also, it's indicative of a player's ability to reduce the effectiveness of passes and create turnovers." },
    { code:'PS', name:'Passing',        type:'technical',   zone:'All over the floor',
      desc:"This is a player's ability to make good fundamental passes. A higher passing rating means fewer turnovers as well as a better pass being delivered to a potential shooter, which will increase the effectiveness of his shot." },
    { code:'BH', name:'Ball Handling',  type:'technical',   zone:'The backcourt & driving lanes',
      desc:"This trait is all about dribbling and handling the ball. A high BH score indicates a player who is less likely to turn the ball over and more effective when driving to the basket. Clearly this is most important for point guards and players who attack the hoop." },
    { code:'RB', name:'Rebounding',     type:'technical',   zone:'On the glass, both ends',
      desc:"This trait represents a player's technical know-how when fighting for rebounds. A high RB score means a player is proficient at reading missed shots and getting into good rebounding position. It also indicates a player's ability to box out an opponent." },
    { code:'ST', name:'Strength',       type:'physical',    zone:'In the paint & on contact',
      desc:"This is the measure of how strong a player is. This trait comes into play when attempting to score or defend near the basket, fighting for a good shot when driving to the hoop, when rebounding, and when setting or fighting through screens." },
    { code:'AG', name:'Agility',        type:'physical',    zone:'Perimeter & transition',
      desc:"An indication of a player's foot speed. A high AG score will be very important when driving to the basket on offense, playing perimeter defense and covering a lot of ground as a zone defender." },
    { code:'ND', name:'Endurance',      type:'physical',    zone:'Every minute on the floor',
      desc:"This represents a player's conditioning and willingness to fight through fatigue. Players with high ND scores will tire less. As a player's energy level erodes during gameplay, you'll notice he loses effectiveness in all traits across the board." },
    { code:'IQ', name:'Basketball IQ',  type:'intangibles', zone:'Everywhere',
      desc:"Basketball IQ is the closest thing you'll get to understanding a player's intangibles. Players who score high in this trait do many of the little things well. Getting teammates involved, making clutch plays and committing fewer fouls are just a few examples." },
    { code:'FT', name:'Free Throws',    type:'intangibles', zone:'At the line',
      desc:"Exactly what you would expect. This trait indicates a player's ability at the charity stripe. Note this is a different skill than SH as it requires a different type of technical discipline and mental focus." },
    { code:'EM', name:'Emotion',        type:'intangibles', zone:'Locker room, bench & huddle', special:'emotion',
      desc:"" },
    { code:'MO', name:'Momentum',       type:'intangibles', zone:'The flow of the game', special:'momentum',
      desc:"Strictly an in-game measure. Players start each game with 0 momentum, and the value toggles up or down based on the flow of the game, their team's performance, and their individual performance. Timeouts and quarter breaks will bring each player's momentum closer to equilibrium. Valuable to reset your cold players and slow down your opponent's hot players." }
  ];

  function emotionMeter() {
    var faces = [['😎','Happiest'], ['😊','Happy'], ['😐','Neutral'], ['😕','Unhappy'], ['😡','Disruptive']];
    return '<div class="meter-wrap"><div class="meter-cap">The mood scale</div><div class="emotion-meter">' +
      faces.map(function (f) { return '<div class="em-step"><span class="em-face">' + f[0] + '</span><span class="em-lbl">' + f[1] + '</span></div>'; }).join('') +
      '</div></div>';
  }
  function momentumMeter() {
    return '<div class="meter-wrap"><div class="meter-cap">In-game swing</div><div class="mo-meter">' +
      '<span class="mo-end cold">Cold</span>' +
      '<div class="mo-track"><span class="mo-zero">0</span><span class="mo-fill"></span><span class="mo-needle"></span></div>' +
      '<span class="mo-end hot">Hot</span></div></div>';
  }

  function renderReference() {
    var host = document.getElementById('attr-reference');
    if (!host) return;
    var order = ['offense', 'defense', 'technical', 'physical', 'intangibles'];
    host.innerHTML = order.map(function (key) {
      var t = TYPES[key];
      var list = ATTRS.filter(function (a) { return a.type === key; });
      var cards = list.map(function (a) {
        var meter = a.special === 'emotion' ? emotionMeter() : a.special === 'momentum' ? momentumMeter() : '';
        return '<div class="attr-card' + (meter ? ' attr-card--wide' : '') + '" style="--ac:' + t.color + '">' +
            '<span class="ac-badge" style="background:' + t.color + ';color:' + t.ink + '">' + a.code + '</span>' +
            '<span class="ac-main">' +
              '<span class="ac-name">' + a.name + '</span>' +
              '<span class="ac-zone">◎ Matters most: <strong>' + a.zone + '</strong></span>' +
              (a.desc ? '<span class="ac-desc">' + a.desc + '</span>' : '') +
              meter +
            '</span>' +
          '</div>';
      }).join('');
      return '<div class="attr-group">' +
          '<div class="ag-head"><span class="ag-dot" style="background:' + t.color + '"></span>' +
          '<h3>' + t.label + '</h3><span class="ag-n">' + list.length + '</span></div>' +
          '<div class="ag-cards">' + cards + '</div>' +
        '</div>';
    }).join('');
  }

  /* dead "next lesson" handoff button — toast (matches hub behavior) */
  var toastTimer;
  function wire() {
    document.body.addEventListener('click', function (e) {
      var s = e.target.closest('[data-soon]');
      if (!s) return;
      e.preventDefault();
      sfx('click-tiny.wav');
      var t = document.getElementById('toast');
      if (!t) return;
      t.querySelector('.tt').textContent = 'Lesson coming soon';
      t.querySelector('.ts').textContent = 'Training is part of the next build pass.';
      t.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () { t.classList.remove('show'); }, 3000);
    });
  }

  renderReference();
  wire();
  // single hook that lights up the hub's progress meter, explored ✓, and next-up cue
  if (window.GOB) window.GOB.markSeen('player-attributes');
})();
