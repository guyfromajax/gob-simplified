import json
from types import SimpleNamespace

from scripts import verify_deploy


class _Response:
    def __init__(self, body: str, status: int = 200):
        self._body = body.encode()
        self._status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body

    def getcode(self):
        return self._status


def setup_function():
    verify_deploy.RESULTS.clear()


def test_build_verification_checks_commit_and_production_identity(monkeypatch):
    health = {
        "commit": "abcdef123456",
        "hash_seed": "0",
        "environment": "production",
        "database": "gob",
        "db_access": "write",
    }
    monkeypatch.setattr(
        verify_deploy.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(json.dumps(health)),
    )

    verify_deploy.verify_build("https://backend.example/health", "abcdef123456789")

    assert verify_deploy.RESULTS
    assert all(ok for ok, _message in verify_deploy.RESULTS)


def test_build_verification_rejects_wrong_database_identity(monkeypatch):
    health = {
        "commit": "abcdef123456",
        "hash_seed": "0",
        "environment": "staging",
        "database": "gob-staging",
        "db_access": "write",
    }
    monkeypatch.setattr(
        verify_deploy.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(json.dumps(health)),
    )

    verify_deploy.verify_build("https://backend.example/health", "abcdef123456")

    failures = [message for ok, message in verify_deploy.RESULTS if not ok]
    assert any("environment is production" in message for message in failures)
    assert any("database is gob" in message for message in failures)


def test_hosted_ci_requires_completed_success_for_commit(monkeypatch):
    payload = json.dumps([
        {"status": "completed", "conclusion": "success", "databaseId": 12, "url": "https://ci.example/12"}
    ])
    monkeypatch.setattr(
        verify_deploy.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=payload, stderr=""),
    )

    verify_deploy.verify_hosted_ci("abcdef123456")

    assert verify_deploy.RESULTS == [
        (True, "Run Tests completed successfully for commit abcdef123456 (matching runs=1, successful=1)")
    ]


def test_hosted_ci_rejects_pending_or_failed_runs(monkeypatch):
    payload = json.dumps([
        {"status": "completed", "conclusion": "failure", "databaseId": 12, "url": "https://ci.example/12"},
        {"status": "in_progress", "conclusion": "", "databaseId": 13, "url": "https://ci.example/13"},
    ])
    monkeypatch.setattr(
        verify_deploy.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=payload, stderr=""),
    )

    verify_deploy.verify_hosted_ci("abcdef123456")

    assert verify_deploy.RESULTS[-1][0] is False


def test_smoke_check_rejects_maintenance_page(monkeypatch):
    monkeypatch.setattr(
        verify_deploy.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response("<html><title>Maintenance</title></html>"),
    )

    verify_deploy.verify_smoke_url("https://app.example/homepage.html")

    assert verify_deploy.RESULTS[-1][0] is False
    assert "maintenance page" in verify_deploy.RESULTS[-1][1]
