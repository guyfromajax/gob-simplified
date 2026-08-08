"""The dynamic-recruit borrow pool must exclude recruit_ids whose kit asset doesn't
exist in R2 — so an expanded set with not-yet-arted ids never hands a portrait-less id
to a dynamic draw. File-existence via a single R2 LIST, cached, degrading to UNFILTERED
(never empty) when R2 is unavailable so generation never breaks."""
from unittest.mock import patch, Mock

import BackEnd.models.recruit_sets as rs


def _db_with(recruit_ids, flags=None):
    """flags: optional {recruit_id: has_portrait_bool} to stamp has_portrait."""
    flags = flags or {}
    db = Mock()
    col = Mock()
    recs = []
    for r in recruit_ids:
        d = {"recruit_id": r}
        if r in flags:
            d["has_portrait"] = flags[r]
        recs.append(d)
    col.find_one.return_value = {"recruits": recs}
    db.__getitem__ = Mock(return_value=col)
    return db


def _reset_cache():
    rs._kit_ids_cache["ids"] = None


def test_pool_filters_to_ids_with_a_kit_asset():
    _reset_cache()
    db = _db_with(["a", "b", "c"])  # c has no kit
    with patch("BackEnd.services.r2_images.is_configured", return_value=True), \
         patch("BackEnd.services.r2_images.list_keys",
               return_value=["recruits/kit/a.png", "recruits/kit/b.png", "recruits/kit/b.mask.png"]):
        pool = rs._base_image_pool(db)
    assert set(pool) == {"a", "b"}, "portrait-less id 'c' must be filtered out"
    assert "b" in pool and pool.count("b") == 1, "mask.png must not create a phantom id"


def test_r2_error_falls_back_to_has_portrait_flag():
    """R2 down → fail SAFE: exclude has_portrait=false ids (not-yet-arted), not pass all."""
    _reset_cache()
    db = _db_with(["a", "b", "c"], flags={"a": True, "b": True, "c": False})
    with patch("BackEnd.services.r2_images.is_configured", return_value=True), \
         patch("BackEnd.services.r2_images.list_keys", side_effect=RuntimeError("R2 down")):
        pool = rs._base_image_pool(db)
    assert set(pool) == {"a", "b"}, "flagged-false id must be excluded when R2 is unreachable"


def test_r2_error_without_flags_stays_unfiltered():
    """Backward-compat: R2 down + no has_portrait flags → unfiltered (never empty)."""
    _reset_cache()
    db = _db_with(["a", "b", "c"])
    with patch("BackEnd.services.r2_images.is_configured", return_value=True), \
         patch("BackEnd.services.r2_images.list_keys", side_effect=RuntimeError("R2 down")):
        pool = rs._base_image_pool(db)
    assert set(pool) == {"a", "b", "c"}


def test_pool_unfiltered_when_r2_unconfigured():
    _reset_cache()
    db = _db_with(["a", "b", "c"])
    with patch("BackEnd.services.r2_images.is_configured", return_value=False):
        pool = rs._base_image_pool(db)
    assert set(pool) == {"a", "b", "c"}, "unconfigured R2 → unfiltered (current behaviour)"


def test_available_kit_ids_is_computed_once():
    _reset_cache()
    with patch("BackEnd.services.r2_images.is_configured", return_value=True), \
         patch("BackEnd.services.r2_images.list_keys", return_value=["recruits/kit/a.png"]) as lk:
        rs._available_kit_ids(); rs._available_kit_ids(); rs._available_kit_ids()
    assert lk.call_count == 1, "R2 must be listed once per process, not per draw"
