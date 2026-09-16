"""An empty or failed defense-catalog load must not be cached as final.

These tests never touch a collection: the catalog reader and the clock are patched, so the
cache state machine is exercised in isolation.
"""
import logging

import pytest

from BackEnd.utils import defense_identity as DI
from BackEnd.utils.defense_utils import is_zone_defense

ZONE_DOCS = [
    {"_id": "a", "defense_id": "base-man", "defense_type": "Man", "name": "Base Man"},
    {"_id": "b", "defense_id": "2-3-zone", "defense_type": "Zone", "name": "2-3 Zone"},
    {"_id": "c", "defense_id": "3-2-zone", "defense_type": "Zone", "name": "3-2 Zone"},
    {"_id": "d", "defense_id": "1-3-1-zone", "defense_type": "Zone", "name": "1-3-1 Zone"},
]


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now


class _Reader:
    """Serves one scripted result per read: a list of docs, or an exception to raise."""

    def __init__(self, *results):
        self.results = list(results)
        self.reads = 0

    def __call__(self):
        self.reads += 1
        result = self.results[min(self.reads, len(self.results)) - 1]
        if isinstance(result, Exception):
            raise result
        return list(result)


@pytest.fixture
def catalog(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(DI.time, "monotonic", clock.monotonic)
    DI.clear_defense_identity_cache()

    def install(*results):
        reader = _Reader(*results)
        monkeypatch.setattr(DI, "_read_catalog_documents", reader)
        return reader

    yield install, clock
    DI.clear_defense_identity_cache()


def test_empty_first_load_recovers_after_backoff(catalog):
    install, clock = catalog
    reader = install([], ZONE_DOCS)

    assert is_zone_defense("3-2-zone") is False
    assert DI.defense_catalog_status() == "empty"

    # Inside the retry window: no re-read (keeps the one-read-per-window perf guard).
    for _ in range(50):
        assert is_zone_defense("3-2-zone") is False
    assert reader.reads == 1

    clock.now += DI.DEFENSE_CATALOG_RETRY_SECONDS + 0.1
    assert is_zone_defense("3-2-zone") is True
    assert DI.defense_catalog_status() == "loaded"
    assert DI.defense_zone_shell_variant("1-3-1-zone") == "131"
    assert reader.reads == 2

    # Loaded is final.
    clock.now += 10 * DI.DEFENSE_CATALOG_RETRY_SECONDS
    assert is_zone_defense("2-3-zone") is True
    assert reader.reads == 2


def test_failed_first_load_degrades_without_raising_then_recovers(catalog):
    install, clock = catalog
    reader = install(RuntimeError("server selection timeout"), ZONE_DOCS)

    assert is_zone_defense("2-3-zone") is False
    assert DI.defense_catalog_status() == "failed"
    clock.now += DI.DEFENSE_CATALOG_RETRY_SECONDS + 0.1
    assert is_zone_defense("2-3-zone") is True
    assert reader.reads == 2


def test_explicit_refresh_still_raises_on_read_failure(catalog):
    install, _ = catalog
    install(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        DI.refresh_defense_identity_cache()
    assert DI.defense_catalog_status() == "failed"


def test_poison_final_empty_cache_stays_man_only(catalog, monkeypatch):
    """Reinstates the old behaviour (an empty load never retried): the recovery assertion
    above must fail under it, proving the test detects the defect."""
    install, clock = catalog
    install([], ZONE_DOCS)
    monkeypatch.setattr(DI, "DEFENSE_CATALOG_RETRY_SECONDS", float("inf"))
    assert is_zone_defense("3-2-zone") is False
    clock.now += 1e9
    assert is_zone_defense("3-2-zone") is False


def test_degraded_substitution_announces_every_time(catalog, caplog):
    install, _ = catalog
    install([])
    caplog.set_level(logging.WARNING, logger=DI.logger.name)

    for _ in range(3):
        assert DI.announce_zone_played_as_man("3-2-zone", "HCO possession") == "3-2"
    subs = [r for r in caplog.records if "DEFENSE-IDENTITY SUBSTITUTION" in r.getMessage()]
    assert len(subs) == 3
    assert "'3-2-zone'" in subs[0].getMessage() and "empty" in subs[0].getMessage()

    # Man calls are never substitutions.
    caplog.clear()
    assert DI.announce_zone_played_as_man("base-man", "HCO possession") is None
    assert DI.announce_zone_played_as_man("man", "HCO possession") is None
    assert not [r for r in caplog.records if "SUBSTITUTION" in r.getMessage()]


def test_degraded_label_does_not_claim_a_zone(catalog):
    install, _ = catalog
    install([])
    for call, short in (("2-3-zone", "2-3"), ("3-2-zone", "3-2"), ("1-3-1-zone", "1-3-1")):
        label = DI.defense_playcall_display_label(call)
        assert label == f"Man ({short} unavailable)"
        # scoreboardDefenseBucket (defenseUi.js) buckets anything containing "zone" as Zone.
        assert "zone" not in label.lower()


def test_loaded_catalog_label_and_no_announcement(catalog, caplog):
    install, _ = catalog
    install(ZONE_DOCS)
    caplog.set_level(logging.WARNING, logger=DI.logger.name)
    assert DI.defense_playcall_display_label("3-2-zone") == "3-2 Zone"
    assert DI.announce_zone_played_as_man("3-2-zone", "HCO possession") is None
    assert not [r for r in caplog.records if "SUBSTITUTION" in r.getMessage()]
