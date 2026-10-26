"""Pytest fixtures and test environment setup."""

import pytest
from pathlib import Path
import tempfile
from backend.app.core.config import settings
from backend.app.core.database import init_db, purge_all_data


@pytest.fixture(autouse=True)
def test_environment(tmp_path: Path, monkeypatch):
    """Isolates database and HMAC keys in a temporary directory for each test run."""
    db_file = tmp_path / "test_numbershield.db"
    key_file = tmp_path / ".test_key"
    
    monkeypatch.setattr(settings, "db_path", db_file)
    monkeypatch.setattr(settings, "key_path", key_file)
    
    init_db(db_file)
    yield
    purge_all_data(db_file, key_file)
