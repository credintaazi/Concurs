from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "quiz"
    db_password: str = ""
    db_name: str = "quiz"
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = ""
    app_origins: str = "http://localhost:8080,http://localhost:5173"
    cookie_secure: bool = False
    session_days: int = 30

    @property
    def origins(self) -> list[str]:
        return [s.strip().rstrip("/") for s in self.app_origins.split(",") if s.strip()]

    @property
    def db_url(self):
        if self.database_url:
            return self.database_url
        if "db_host" not in self.model_fields_set:
            return URL.create("sqlite", database=str(Path(__file__).resolve().parents[2] / ".local" / "quiz.sqlite3"))
        return URL.create(
            "postgresql+psycopg", username=self.db_user, password=self.db_password,
            host=self.db_host, port=self.db_port, database=self.db_name,
        )


settings = Settings()
