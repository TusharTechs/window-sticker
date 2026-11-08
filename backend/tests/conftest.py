import pytest


@pytest.fixture(autouse=True)
def _no_analyst(monkeypatch):
    """Scripted inference answers in order, so an extra analyst call would steal a turn.
    The analyst has its own tests; everywhere else it is off."""
    monkeypatch.setenv("WSK_ANALYST_MODEL", "")
