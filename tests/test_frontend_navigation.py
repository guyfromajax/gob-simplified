import json
import subprocess
from pathlib import Path
import pytest

@pytest.mark.xfail(reason="bootGame popup rendering changed to module-based completion popup", strict=False)
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
 global.window = {{ location: {{ search: '?mode=franchise&franchise_id=test123&game_id=dummy' }} }};
 global.alert = () => {{}};
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


def test_bootgame_includes_game_id_for_franchise_and_tournament_reads():
    boot_path = Path('FrontEnd/static/js/phaser/bootGame.js').resolve()
    script = boot_path.read_text()

    load_gameplan_start = script.index("async function loadGamePlanSettings()")
    load_playbook_start = script.index("async function loadPlaybookSettings()")
    load_playbook_end = script.index("let periodLabel", load_playbook_start)

    load_gameplan_block = script[load_gameplan_start:load_playbook_start]
    load_playbook_block = script[load_playbook_start:load_playbook_end]

    assert "if (gameId) {" in load_gameplan_block
    assert "params.set('game_id', gameId);" in load_gameplan_block
    assert "if (mode === 'franchise' && franchiseId)" in load_gameplan_block
    assert "else if (mode === 'single' && gameId)" not in load_gameplan_block

    assert "if (gameId) {" in load_playbook_block
    assert "params.set('game_id', gameId);" in load_playbook_block
    assert "if (mode === 'franchise' && franchiseId)" in load_playbook_block
    assert "else if (mode === 'single' && gameId)" not in load_playbook_block
