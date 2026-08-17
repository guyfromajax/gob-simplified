/* Recruits leaning your way — fixture for the FCC Recruits tab mock.
   Shape follows the FCC recruits table: name, homeRegion, archetype, ht, wt, pos, yr,
   12 attrs (0-10 display scale), rt current/potential, and a lean ladder standing. */
(function () {
  var KEYS = ['SC','SH','ID','OD','PS','BH','RB','ST','AG','ND','IQ','FT'];
  // lean: [yourRank (1-3) or 0 = not on list, [slot tokens]]
  var R = [
    ['Isaiah Frame','Region A','Slasher','SF','HS',78,206,68,88,[8,5,4,6,4,7,5,5,8,6,6,5],1,['YOU','Tulsa St','Open']],
    ['Marquis Dell','Region B','Rim Protector','C','HS',82,244,64,86,[5,2,9,3,2,2,9,8,4,5,5,3],1,['YOU','Ann Arbor','Bayou']],
    ['Wendell Pace','Region C','Floor General','PG','HS',74,181,61,82,[5,5,3,6,9,9,2,3,7,7,8,6],2,['Appalachia','YOU','Open']],
    ['Trey Mondragon','Region D','Sharpshooter','SG','HS',75,187,59,79,[6,9,2,4,4,5,2,3,5,5,6,9],1,['YOU','Open','Open']],
    ['Chauncey Bell','Region E','Two-Way Wing','SF','HS',77,199,57,77,[6,6,5,7,5,6,5,4,7,6,6,6],2,['Austin','YOU','Abilene']],
    ['Ruben Oyelaran','Region F','Stretch Four','PF','HS',80,221,54,80,[6,7,5,4,3,3,7,6,5,5,5,6],3,['Barton','Ada','YOU']],
    ['Dov Kestenbaum','Region G','Combo Guard','SG','HS',73,178,51,71,[5,6,2,5,6,7,2,2,6,6,7,7],0,['Bentley','Truman','Open']],
    ['Amos Whitcomb','Region H','Glass Cleaner','PF','HS',79,214,48,69,[4,3,6,3,2,2,9,7,4,6,4,4],2,['Amarillo','YOU','Open']]
  ];

  window.GOB_RECRUITS = {
    ATTR_KEYS: KEYS,
    recruits: R.map(function (r) {
      var attrs = {};
      KEYS.forEach(function (k, i) { attrs[k] = r[9][i]; });
      return {
        name: r[0], homeRegion: r[1], archetype: r[2], pos: r[3], year: r[4],
        heightIn: r[5], height: Math.floor(r[5] / 12) + "'" + (r[5] % 12) + '"',
        weight: r[6], rt: r[7], rtPot: r[8], attrs: attrs,
        leanRank: r[10], leanSlots: r[11]
      };
    })
  };
})();
