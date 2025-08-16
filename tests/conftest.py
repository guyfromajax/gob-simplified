import os
import sys

import pytest

# Ensure the project root is on sys.path so 'import BackEnd' succeeds
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.models.game_manager import GameManager
from BackEnd.constants import POSITION_LIST

@pytest.fixture
def mock_game_manager():
    # Uses team names that must exist in your database
    gm = GameManager("Lancaster", "Bentley-Truman")
    return gm

@pytest.fixture
def simulated_game():
    gm = GameManager("Lancaster", "Bentley-Truman")
    gm.simulate_macro_turn()
    return gm


