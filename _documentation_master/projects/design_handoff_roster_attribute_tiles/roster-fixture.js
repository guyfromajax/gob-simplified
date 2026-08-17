/* Fixture for the Team Roster redesign prototype.
   Attribute values are the 0-10 display scale (production stores 0-100 and floors /10).
   Per-game inputs are defined; season totals + percentages are derived so every
   number on the page is internally consistent. */
(function () {
  var GP = 11;

  // jersey, name, pos, year, height (in), weight, rt current/potential (numeric),
  // attrs on the 0-10 display scale, per-game inputs for the stats view.
  var P = [
    ['2','Kermit Prospect','C','JR',81,242,72,83,[7,2,10,3,3,3,7,6,3,4,4,3],{fga:6.4,fg:.549,tpa:0.1,tp:.0,fta:3.2,ft:.61,reb:5.7,ast:0.8,stl:0.4,blk:1.6,f:2.1,to:1.1,defa:6.1,def:.59,scra:4.4,scr:.62}],
    ['7','Trent Athens','SF','SR',79,228,74,79,[8,10,7,9,4,4,5,4,10,5,4,6],{fga:15.5,fg:.508,tpa:3.1,tp:.361,fta:5.0,ft:.744,reb:3.0,ast:2.2,stl:1.3,blk:0.4,f:1.8,to:2.4,defa:7.2,def:.64,scra:2.1,scr:.55}],
    ['17','Omar Nola','PF','JR',78,213,71,76,[5,3,3,3,2,2,10,9,6,6,5,4],{fga:4.6,fg:.521,tpa:0.2,tp:.2,fta:2.1,ft:.66,reb:4.8,ast:0.5,stl:0.5,blk:0.9,f:2.0,to:0.9,defa:5.4,def:.61,scra:3.9,scr:.6}],
    ['44','CJ Castleman','PF','SR',79,229,70,74,[5,6,3,3,4,2,8,8,7,6,4,7],{fga:6.8,fg:.531,tpa:0.2,tp:.2,fta:2.6,ft:.688,reb:10.7,ast:0.6,stl:0.7,blk:1.1,f:2.4,to:1.3,defa:6.6,def:.63,scra:4.8,scr:.64}],
    ['13','Freddie Anderson','PF','JR',77,205,66,68,[3,5,3,3,3,2,8,7,5,5,5,4],{fga:3.4,fg:.49,tpa:0.4,tp:.25,fta:1.2,ft:.63,reb:3.4,ast:0.4,stl:0.3,blk:0.6,f:1.5,to:0.7,defa:4.1,def:.58,scra:3.1,scr:.58}],
    ['20','Clint Workman','SF','SR',76,203,62,65,[6,4,5,7,3,3,4,3,7,3,4,4],{fga:4.2,fg:.47,tpa:1.4,tp:.31,fta:1.1,ft:.7,reb:2.1,ast:0.9,stl:0.6,blk:0.2,f:1.3,to:0.8,defa:4.6,def:.57,scra:1.9,scr:.54}],
    ['32','Ronnie Rozier','C','SO',80,218,58,61,[5,4,4,3,3,2,8,6,4,4,4,4],{fga:2.9,fg:.5,tpa:0.0,tp:.0,fta:1.0,ft:.55,reb:2.9,ast:0.3,stl:0.2,blk:0.7,f:1.4,to:0.6,defa:3.3,def:.55,scra:2.6,scr:.57}],
    ['0','Xenon Fletcher','PG','FR',72,189,55,84,[5,3,2,6,5,5,2,2,6,3,6,3],{fga:4.4,fg:.412,tpa:2.1,tp:.31,fta:1.6,ft:.72,reb:0.4,ast:5.1,stl:1.1,blk:0.1,f:1.4,to:2.1,defa:5.8,def:.62,scra:1.2,scr:.5}],
    ['4','Kent McManus','SG','SR',72,175,52,54,[1,8,1,2,3,2,1,2,3,3,4,9],{fga:9.1,fg:.463,tpa:5.4,tp:.402,fta:1.4,ft:.891,reb:0.1,ast:1.0,stl:0.6,blk:0.0,f:1.1,to:0.9,defa:4.9,def:.47,scra:1.6,scr:.52}],
    ['11','Delmont Braggs','SG','JR',75,201,48,52,[4,6,2,5,2,3,2,2,3,4,3,4],{fga:3.1,fg:.44,tpa:1.6,tp:.29,fta:0.8,ft:.68,reb:1.2,ast:0.8,stl:0.4,blk:0.1,f:1.0,to:0.7,defa:3.4,def:.52,scra:1.4,scr:.5}],
    ['25','Von Sanborn','PG','FR',70,170,44,51,[1,1,2,3,2,6,1,1,4,3,4,3],{fga:1.9,fg:.39,tpa:0.7,tp:.24,fta:0.5,ft:.66,reb:0.6,ast:1.4,stl:0.3,blk:0.0,f:0.8,to:0.9,defa:2.6,def:.5,scra:0.8,scr:.48}],
    ['16','Jedidiah Ballard','C','SO',78,211,42,44,[3,2,5,2,1,2,4,4,1,3,3,2],{fga:1.3,fg:.42,tpa:0.0,tp:.0,fta:0.6,ft:.5,reb:1.3,ast:0.2,stl:0.1,blk:0.4,f:0.9,to:0.5,defa:2.1,def:.48,scra:1.1,scr:.46}]
  ];

  var PS = [
    ['—','Marcus Deese','SG','SO',74,186,39,46,[3,4,2,3,2,3,2,2,3,3,3,4],{fga:2.4,fg:.42,tpa:1.1,tp:.27,fta:0.7,ft:.6,reb:1.1,ast:0.6,stl:0.3,blk:0.1,f:0.9,to:0.8,defa:2.4,def:.49,scra:1.0,scr:.47}],
    ['—','Terry Alcott','PF','FR',77,198,36,49,[2,2,3,2,1,1,4,4,2,3,2,3],{fga:1.7,fg:.4,tpa:0.0,tp:.0,fta:0.6,ft:.52,reb:2.2,ast:0.2,stl:0.2,blk:0.4,f:1.1,to:0.6,defa:2.0,def:.46,scra:1.4,scr:.45}],
    ['—','Bo Lattimer','PG','FR',71,168,33,45,[2,2,1,2,3,4,1,1,2,2,3,2],{fga:1.4,fg:.37,tpa:0.6,tp:.22,fta:0.4,ft:.58,reb:0.5,ast:1.1,stl:0.3,blk:0.0,f:0.7,to:0.9,defa:1.8,def:.44,scra:0.6,scr:.44}]
  ];

  var KEYS = ['SC','SH','ID','OD','PS','BH','RB','ST','AG','ND','IQ','FT'];

  function round(v) { return Math.round(v); }

  function build(rows) {
    return rows.map(function (r) {
      var attrs = {};
      KEYS.forEach(function (k, i) { attrs[k] = r[8][i]; });
      var g = r[9], gp = GP;
      var fga = round(g.fga * gp), fgm = round(fga * g.fg);
      var tpa = round(g.tpa * gp), tpm = round(tpa * g.tp);
      var fta = round(g.fta * gp), ftm = round(fta * g.ft);
      if (tpm > fgm) tpm = fgm;
      var treb = round(g.reb * gp), oreb = round(treb * 0.3);
      var defa = round(g.defa * gp), defs = round(defa * g.def);
      var scra = round(g.scra * gp), scrs = round(scra * g.scr);
      var pts = 2 * (fgm - tpm) + 3 * tpm + ftm;
      return {
        jersey: r[0], name: r[1], pos: r[2], year: r[3],
        heightIn: r[4], height: Math.floor(r[4] / 12) + "'" + (r[4] % 12) + '"',
        weight: r[5], rt: r[6], rtPot: r[7],
        attrs: attrs,
        stats: {
          GP: gp, PTS: pts, FGM: fgm, FGA: fga, '3PTM': tpm, '3PTA': tpa,
          FTM: ftm, FTA: fta, DREB: treb - oreb, OREB: oreb, TREB: treb,
          AST: round(g.ast * gp), STL: round(g.stl * gp), BLK: round(g.blk * gp),
          F: round(g.f * gp), TO: round(g.to * gp),
          DEFA: defa, DEFS: defs, SCRA: scra, SCRS: scrs
        }
      };
    });
  }

  var roster = build(P);
  var squad = build(PS);

  // Projected starting five, by lineup order.
  var five = ['Xenon Fletcher', 'Kent McManus', 'Trent Athens', 'CJ Castleman', 'Kermit Prospect'];

  window.GOB_ROSTER = {
    GP: GP,
    ATTR_KEYS: KEYS,
    team: { name: 'Four Corners', slug: 'four_corners', record: '9-2', conference: 'Conference 14', standing: '2nd' },
    players: roster,
    squad: squad,
    startingFive: five.map(function (n) { return roster.find(function (p) { return p.name === n; }); })
  };
})();
