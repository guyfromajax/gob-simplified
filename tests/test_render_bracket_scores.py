import json
import subprocess
import textwrap
from pathlib import Path


def test_render_bracket_displays_scores():
    js_path = Path('FrontEnd/static/tournament.js').resolve()
    node_template = """
    const fs = require('fs');
    const vm = require('vm');
    const code = fs.readFileSync(__PATH__, 'utf8');
    const script = code;
    const originalLog = console.log;
    console.log = () => {};
    global.window = { DEBUG_BRACKET: false };
    global.formatTeamName = (n) => n;
    const tournamentData = {
      bracket: {
        round1: [
          {home_team:'Alpha', away_team:'Bravo', game_id:null, winner:'Alpha', score:{Alpha:70, Bravo:65}},
          {home_team:'Charlie', away_team:'Delta', game_id:null, winner:'Delta', score:{Charlie:60, Delta:80}},
          {home_team:'Echo', away_team:'Foxtrot', game_id:null, winner:'Foxtrot', score:{Echo:55, Foxtrot:85}},
          {home_team:'Golf', away_team:'Hotel', game_id:null, winner:'Golf', score:{Golf:75, Hotel:72}}
        ],
        round2: [],
        final: []
      },
      results: [
        {round:1, match_index:0, home_team:'Alpha', away_team:'Bravo', score:{Alpha:70,Bravo:65}, winner:'Alpha'},
        {round:1, match_index:1, home_team:'Charlie', away_team:'Delta', score:{Charlie:60,Delta:80}, winner:'Delta'},
        {round:1, match_index:2, home_team:'Echo', away_team:'Foxtrot', score:{Echo:55,Foxtrot:85}, winner:'Foxtrot'},
        {round:1, match_index:3, home_team:'Golf', away_team:'Hotel', score:{Golf:75,Hotel:72}, winner:'Golf'}
      ],
      current_round:2
    };
    global.localStorage = { getItem: () => JSON.stringify(tournamentData), setItem: () => null };
    const bracketEl = {
        children: [],
        style: {},
        appendChild(child) { this.children.push(child); },
        set innerHTML(v) { this.children = []; }
    };
    global.document = {
      getElementById(id) { return bracketEl; },
      addEventListener() {},
      createElement(tag) { const el = {
         tagName: tag,
         className: '',
         style: {},
         children: [],
         appendChild(child) { this.children.push(child); },
         set textContent(v) { this._text = v; },
         get textContent() { return this._text; },
         set innerHTML(v) { this._innerHTML = v; },
         get innerHTML() { return this._innerHTML || ''; }
      }; el.classList = { add(cls){ el.className += (el.className ? ' ' : '') + cls; } }; return el; }
    };
    vm.runInThisContext(script);
    renderBracket();
    const scores = [];
    function collect(node) {
        if(node.className && node.className.includes('score') && node.textContent !== undefined){
            scores.push(node.textContent);
        }
        if(node.children) node.children.forEach(collect);
    }
    bracketEl.children.forEach(collect);
    console.log = originalLog;
    console.log(JSON.stringify(scores));
    """
    node_script = textwrap.dedent(node_template).replace('__PATH__', json.dumps(str(js_path)))
    result = subprocess.check_output(['node', '-e', node_script])
    scores = json.loads(result.decode().strip())
    assert 70 in scores and 65 in scores
