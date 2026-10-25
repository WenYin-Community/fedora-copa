import pytest


@pytest.fixture(autouse=True)
def _force_english_locale(monkeypatch):
    """Keep assertions deterministic regardless of the developer's locale."""
    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.delenv("LANGUAGE", raising=False)
