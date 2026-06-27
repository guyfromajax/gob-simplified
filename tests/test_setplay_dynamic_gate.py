"""Dynamic HCO Set Plays — Stage A: feature gate + up-front-event skip wiring."""
import os
import importlib
import BackEnd.engine.phase_resolution as PR


def _set_env(monkeypatch, **kv):
    for k, v in kv.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_setplay_gate_off_by_default(monkeypatch):
    monkeypatch.delenv("GOB_DYNAMIC_HCO_SETPLAY", raising=False)
    assert PR._dynamic_hco_setplay_enabled() is False


def test_setplay_gate_on(monkeypatch):
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("GOB_DYNAMIC_HCO_SETPLAY", v)
        assert PR._dynamic_hco_setplay_enabled() is True


def test_setplay_gate_independent_of_motion(monkeypatch):
    # The two flags are independent — motion ON must not enable set plays.
    monkeypatch.setenv("GOB_DYNAMIC_HCO_MOTION", "1")
    monkeypatch.delenv("GOB_DYNAMIC_HCO_SETPLAY", raising=False)
    assert PR._dynamic_hco_motion_enabled() is True
    assert PR._dynamic_hco_setplay_enabled() is False
