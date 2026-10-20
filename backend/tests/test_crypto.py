import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from app.connections.models import DataSourceConnection, DataSourceProvider
from app.core import crypto
from app.core.config import get_settings


@pytest.fixture
def key(monkeypatch):
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(get_settings(), "data_encryption_key", new_key)
    return new_key


def test_round_trip(key):
    secret = {"access_token": "abc", "refresh_token": "def", "expires_at": 1_800_000_000}
    stored = crypto.encrypt_json(secret)
    assert list(stored) == ["enc"]
    assert "abc" not in stored["enc"]
    assert crypto.decrypt_json(stored) == secret


def test_rows_written_before_encryption_are_read_as_is(key):
    assert crypto.decrypt_json({"api_key": "plain"}) == {"api_key": "plain"}


def test_wrong_key_is_a_clear_error(key, monkeypatch):
    stored = crypto.encrypt_json({"api_key": "k"})
    monkeypatch.setattr(get_settings(), "data_encryption_key", Fernet.generate_key().decode())
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY"):
        crypto.decrypt_json(stored)


def test_key_rotation_reads_old_data_and_writes_with_the_first_key(key, monkeypatch):
    old_stored = crypto.encrypt_json({"api_key": "k"})
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(get_settings(), "data_encryption_key", f"{new_key},{key}")
    assert crypto.decrypt_json(old_stored) == {"api_key": "k"}

    new_stored = crypto.encrypt_json({"api_key": "k"})
    monkeypatch.setattr(get_settings(), "data_encryption_key", new_key)  # old key dropped
    assert crypto.decrypt_json(new_stored) == {"api_key": "k"}


async def test_connection_credentials_are_encrypted_in_the_database(db_session):
    async with db_session() as session:
        session.add(
            DataSourceConnection(
                provider=DataSourceProvider.STRAVA, external_id="12345", credentials={"refresh_token": "s3cret"}
            )
        )
        await session.commit()

    async with db_session() as session:
        raw = (await session.execute(text("SELECT credentials FROM data_source_connections"))).scalar_one()
        assert "s3cret" not in raw
        connection = await session.scalar(select(DataSourceConnection))
        assert connection.credentials == {"refresh_token": "s3cret"}


def test_empty_environment_variables_count_as_unset(monkeypatch):
    """docker-compose passes `X: ${X:-}` through, so unset optional settings arrive as ""."""
    from app.core.config import Settings

    monkeypatch.setenv("STRAVA_WEBHOOK_SUBSCRIPTION_ID", "")
    monkeypatch.setenv("SMTP_PORT", "")
    monkeypatch.setenv("STRAVA_CLIENT_ID", "")
    settings = Settings()
    assert settings.strava_webhook_subscription_id is None
    assert settings.smtp_port == 587
    assert settings.strava_client_id is None
