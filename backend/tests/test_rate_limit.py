from app.core.config import get_settings
from app.core.rate_limit import check_rate_limit, store


def test_rate_limit_blocks_after_limit(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_MS", "60000")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "3")
    get_settings.cache_clear()
    store.clear()
    key = "test-key"

    assert check_rate_limit(key).allowed is True
    assert check_rate_limit(key).allowed is True
    assert check_rate_limit(key).allowed is True
    assert check_rate_limit(key).allowed is False


def test_rate_limit_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()

    assert get_settings().RATE_LIMIT_ENABLED is False
