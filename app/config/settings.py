from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="ATLAS Fatturazione", alias="APP_NAME")
    database_url: str | None = Field(default=None, alias="POSTGRES_CONNECTION_STRING")
    jwt_secret_key: str | None = Field(default=None, alias="JWT_SECRET")
    jwt_expires_minutes: int = Field(default=1440, alias="JWT_EXPIRES_MINUTES")
    mock_login_password: str | None = Field(default=None, alias="MOCKED_LOGIN_PASSWORD")
    allow_origins: str = Field(default="*", alias="ALLOW_ORIGINS")
    public_data_dir: str = Field(default="./data/public", alias="PUBLIC_DATA_DIR")
    assets_dir: str = Field(default="./data/assets", alias="ASSETS_DIR")
    use_proxy: bool = Field(default=False, alias="USE_PROXY")
    scope: str | None = Field(default=None, alias="SCOPE")

    @staticmethod
    def _clean_env_value(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned.startswith("${"):
            return None
        return cleaned

    @model_validator(mode="after")
    def fill_required_from_env(self) -> "Settings":
        self.database_url = self._clean_env_value(self.database_url) or self._clean_env_value(os.environ.get("POSTGRES_CONNECTION_STRING"))
        self.jwt_secret_key = self._clean_env_value(self.jwt_secret_key) or self._clean_env_value(os.environ.get("JWT_SECRET"))
        self.mock_login_password = self._clean_env_value(self.mock_login_password) or self._clean_env_value(os.environ.get("MOCKED_LOGIN_PASSWORD"))
        self.scope = self._clean_env_value(self.scope) or self._clean_env_value(os.environ.get("SCOPE"))
        if not self.database_url:
            raise ValueError("POSTGRES_CONNECTION_STRING is required")
        if not self.jwt_secret_key:
            raise ValueError("JWT_SECRET is required")
        if not self.mock_login_password:
            raise ValueError("MOCKED_LOGIN_PASSWORD is required")
        return self

    def parsed_allow_origins(self) -> list[str]:
        raw = self.allow_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
