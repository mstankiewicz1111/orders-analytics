from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    database_url: str
    idosell_api_base_url: str
    idosell_api_key: str | None = None
    feed_url: str
    admin_token: str = ''
    admin_username: str = 'admin'
    admin_password: str | None = None
    session_secret: str | None = None
    app_timezone: str = 'Europe/Warsaw'
    sync_batch_size: int = 100
    feed_cache_ttl_hours: int = 24
    request_timeout_seconds: int = 60
    table_page_size: int = 100


settings = Settings()
