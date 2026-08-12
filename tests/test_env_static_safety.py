from pathlib import Path

import pytest

from scripts.check_env_safety import scan_repository


def _write_source(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_repository_passes_environment_static_safety_scan():
    assert scan_repository() == []


@pytest.mark.parametrize(
    ("source", "expected_rule"),
    [
        ("from dotenv import load_dotenv\nload_dotenv()\n", "dotenv_loader"),
        ("from pymongo import MongoClient\nclient = MongoClient('x')\n", "mongo_client"),
        ("CONFIG = '.env.production'\n", "production_dotenv"),
        ("URI = 'mongodb://user:password@example.test/gob'\n", "production_uri_literal"),
        (
            "from pathlib import Path\n"
            "for name in ('.env.local', '.env'):\n"
            "    for line in Path(name).read_text().splitlines():\n"
            "        key, value = line.split('=', 1)\n",
            "dotenv_fallback",
        ),
        (
            "from dotenv import dotenv_values\n"
            "values = dotenv_values('.secrets')\n"
            "GOB_DB_ACCESS = values.get('GOB_DB_ACCESS')\n",
            "file_db_authorization",
        ),
    ],
)
def test_unsafe_pattern_fails_scan(tmp_path: Path, source: str, expected_rule: str):
    _write_source(tmp_path, "scripts/unsafe.py", source)
    rules = {violation.rule for violation in scan_repository(tmp_path)}
    assert expected_rule in rules
