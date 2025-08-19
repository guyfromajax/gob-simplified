import { buildDestinations } from '../../FrontEnd/static/js/phaser/animation/freeThrow.js';

const offenseTeam = process.argv[2];
const shooterPos = process.argv[3];

const offenseIsHome = offenseTeam === 'home';

const { oDestinations, dDestinations } = buildDestinations(offenseIsHome, shooterPos);

console.log(JSON.stringify({ oDestinations, dDestinations }));
