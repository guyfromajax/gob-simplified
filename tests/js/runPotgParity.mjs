import fs from 'node:fs';
import { Buffer } from 'node:buffer';

const sourceUrl = new URL('../../FrontEnd/static/js/shared/potg.js', import.meta.url);
const source = fs.readFileSync(sourceUrl, 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const { calculatePlayerOfTheGame } = await import(moduleUrl);

const game = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = calculatePlayerOfTheGame(game, { gameId: String(game._id || game.game_id || '') });
process.stdout.write(JSON.stringify(result));
