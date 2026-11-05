import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


def platform_origins() -> list[str]:
    """Public HTTPS origins announced by common hosting platforms."""
    found = []
    if url := os.environ.get("RENDER_EXTERNAL_URL"):  # Render
        found.append(url)
    if domain := os.environ.get("RAILWAY_PUBLIC_DOMAIN"):  # Railway
        found.append(f"https://{domain}")
    if name := os.environ.get("FLY_APP_NAME"):  # Fly.io
        found.append(f"https://{name}.fly.dev")
    return found


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
    # Built frontend (Vite dist). When set, the API also serves the web app, so a
    # single container can run on a cloud host without a separate Nginx.
    static_dir: str | None = None

    @property
    def origins(self) -> list[str]:
        platform = platform_origins()
        # On a hosting platform, the localhost defaults are dropped unless APP_ORIGINS is set.
        raw = self.app_origins if "app_origins" in self.model_fields_set or not platform else ""
        configured = [s.strip() for s in raw.split(",") if s.strip()]
        return list(dict.fromkeys(s.rstrip("/") for s in configured + platform))

    @property
    def db_url(self):
        if self.database_url:
            # Hosted PostgreSQL providers hand out postgres:// or postgresql:// URLs;
            # this application uses the psycopg 3 driver.
            for prefix in ("postgres://", "postgresql://"):
                if self.database_url.startswith(prefix):
                    return "postgresql+psycopg://" + self.database_url[len(prefix):]
            return self.database_url
        if "db_host" not in self.model_fields_set:
            return URL.create("sqlite", database=str(Path(__file__).resolve().parents[2] / ".local" / "quiz.sqlite3"))
        return URL.create(
            "postgresql+psycopg", username=self.db_user, password=self.db_password,
            host=self.db_host, port=self.db_port, database=self.db_name,
        )


settings = Settings()
