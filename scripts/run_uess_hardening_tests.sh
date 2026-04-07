#!/usr/bin/env bash
set -euo pipefail

pytest \
  tests/test_turn_manager_ownership_contract_unit.py \
  tests/test_simulate_turn_clock_mode_propagation.py \
  tests/test_turn_manager_clock_elapsed_authority_unit.py \
  tests/test_turn_manager_clock_family_coverage.py \
  tests/test_turn_manager_clock_possession_families.py \
  tests/test_turn_manager_clock_shot_families.py \
  tests/test_turn_manager_clock_transition_continuity.py
