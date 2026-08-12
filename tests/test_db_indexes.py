from BackEnd import db as db_module


class _FakeGamesCollection:
    def __init__(self, indexes):
        self.indexes = indexes
        self.create_calls = []

    def list_indexes(self):
        return iter(self.indexes)

    def create_index(self, keys, **options):
        self.create_calls.append((keys, options))


def test_games_franchise_index_accepts_equivalent_legacy_name(monkeypatch):
    collection = _FakeGamesCollection(
        [{"name": "games_franchise_id", "key": {"franchise_id": 1}}]
    )
    monkeypatch.setattr(db_module, "client", object())
    monkeypatch.setattr(db_module, "games_collection", collection)

    db_module.ensure_games_franchise_index()

    assert collection.create_calls == []


def test_games_franchise_index_is_created_when_key_is_absent(monkeypatch):
    collection = _FakeGamesCollection([{"name": "_id_", "key": {"_id": 1}}])
    monkeypatch.setattr(db_module, "client", object())
    monkeypatch.setattr(db_module, "games_collection", collection)

    db_module.ensure_games_franchise_index()

    assert collection.create_calls == [
        ([("franchise_id", 1)], {"name": "franchise_id_1"})
    ]
