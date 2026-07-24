from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/b2b_campaign"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    google_client_id: str = ""
    google_places_api_key: str = ""
    discovery_search_monthly_cap: int = 200
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
