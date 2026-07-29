import pytest

from app.db.seed import _ensure_not_production


def test_seed_guard_raises_when_cookie_secure_true(monkeypatch):
    import app.db.seed as seed_module

    monkeypatch.setattr(seed_module.get_settings(), "cookie_secure", True)
    with pytest.raises(SystemExit):
        _ensure_not_production()


def test_seed_guard_passes_when_cookie_secure_false(monkeypatch):
    import app.db.seed as seed_module

    monkeypatch.setattr(seed_module.get_settings(), "cookie_secure", False)
    _ensure_not_production()
