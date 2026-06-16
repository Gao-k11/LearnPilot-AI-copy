from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Learning Agent Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_port: int = Field(default=8001, alias="APP_PORT")

    database_mode: str = Field(default="mysql", alias="DATABASE_MODE")
    postgres_database_url: str | None = Field(default=None, alias="DATABASE_URL")
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
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    learnpilot_llm_mode: str = Field(default="auto", alias="LEARNPILOT_LLM_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        mode = self.database_mode.lower()
        if mode == "sqlite":
            return self.sqlite_database_url
        if mode == "postgres":
            if not self.postgres_database_url:
                raise ValueError("DATABASE_URL is required when DATABASE_MODE=postgres")
            if self.postgres_database_url.startswith("postgres://"):
                return self.postgres_database_url.replace("postgres://", "postgresql+psycopg2://", 1)
            if self.postgres_database_url.startswith("postgresql://"):
                return self.postgres_database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return self.postgres_database_url
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
