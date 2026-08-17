from BackEnd.api import _bootstrap


def test_health_reports_resolved_railway_database_access(monkeypatch):
    monkeypatch.setenv("MONGO_DB_NAME", "gob")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("GOB_DB_ACCESS", raising=False)

    body = _bootstrap.health_check()

    assert body["db_access"] == "write"
    assert body["environment"] == "production"
    assert body["database"] == "gob"


def test_health_reports_refused_unprivileged_production_access(monkeypatch):
    monkeypatch.setenv("MONGO_DB_NAME", "gob")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("GOB_DB_ACCESS", raising=False)
    for key in tuple(_bootstrap.os.environ):
        if key.startswith("RAILWAY_"):
            monkeypatch.delenv(key, raising=False)

    body = _bootstrap.health_check()

    assert body["db_access"] == "refuse"
