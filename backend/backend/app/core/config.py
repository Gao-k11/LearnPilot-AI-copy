from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Learning Agent Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_port: int = Field(default=8001, alias="APP_PORT")

    database_mode: str = Field(default="mysql", alias="DATABASE_MODE")
    sqlite_database_url: str = Field(default="sqlite:///./learning_agent_demo.db", alias="SQLITE_DATABASE_URL")

    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_database: str = Field(default="learning_agent", alias="MYSQL_DATABASE")

    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    ml_service_url: str = Field(default="http://127.0.0.1:8000", alias="ML_SERVICE_URL")
    use_ml_service: bool = Field(default=True, alias="USE_ML_SERVICE")
    ml_service_timeout_seconds: float = Field(default=15.0, alias="ML_SERVICE_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        if self.database_mode.lower() == "sqlite":
            return self.sqlite_database_url
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_mode.lower() == "sqlite"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
