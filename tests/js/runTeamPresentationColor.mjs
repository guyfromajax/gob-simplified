import {
  readableTeamPresentationColor,
} from '../../FrontEnd/static/js/phaser/utils/matchupsUiShared.js';

console.log(JSON.stringify({
  readablePrimaryStaysPrimary: readableTeamPresentationColor('#f79420', '#ffffff'),
  brighterSecondaryWinsFallback: readableTeamPresentationColor('#111111', '#f2c94c'),
  darkerSecondaryLosesFallback: readableTeamPresentationColor('#d24a1b', '#000000'),
  invalidPrimaryUsesSecondary: readableTeamPresentationColor('invalid', '#f2c94c'),
}));
