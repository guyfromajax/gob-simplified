import json
import subprocess
from pathlib import Path

def test_game_returns_to_command_center_when_franchise_id_missing():
    boot_path = Path('FrontEnd/static/js/phaser/bootGame.js').resolve()
    node_script = f"""
const fs = require('fs');
let script = fs.readFileSync({json.dumps(str(boot_path))}, 'utf8');
script = script.replace(/^import[^\\n]*\\n/gm, '');
const localStorageStore = {{ franchiseId: 'test123' }};
global.localStorage = {{ getItem: (k) => localStorageStore[k] }};
const container = {{ appended: null, appendChild(el) {{ this.appended = el; }} }};
global.document = {{
  getElementById(id) {{ if (id === 'phaser-container') return container; return null; }},
  createElement(tag) {{ return {{ className: '', innerHTML: '', appendChild(){{}} }}; }},
  querySelector(sel) {{ return null; }}
}};
 global.window = {{ location: {{ search: '' }} }};
 global.createGameScene = () => function GameScene(){{}};
 global.Phaser = {{}};
 const originalLog = console.log;
 console.log = () => {{}};
 require('vm').runInThisContext(script);
 showPopup({{homeTeam:'A',homeScore:1,awayTeam:'B',awayScore:2}});
 const href = container.appended.innerHTML.match(/href=\\"([^\\"]+)/)[1];
 console.log = originalLog;
 console.log(JSON.stringify({{ mode, href }}));
"""
    result = subprocess.check_output(['node', '-e', node_script])
    data = json.loads(result.decode().strip())
    assert data['mode'] == 'franchise'
    assert data['href'] == '/franchise/command-center?franchise_id=test123'

