import { getMadeShotSweetSpotGrid } from '../../FrontEnd/static/js/phaser/animation/courtConstants.js';

const home = getMadeShotSweetSpotGrid(true);
const away = getMadeShotSweetSpotGrid(false);
console.log(JSON.stringify({ home, away }));
