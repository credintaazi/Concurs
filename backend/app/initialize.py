"""Idempotent startup: create a fresh SQLite schema or migrate PostgreSQL."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from .db import Base, engine, is_sqlite
from . import models  # Register all tables.


def initialize_database():
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    if not is_sqlite:
        command.upgrade(config, "head")
        return
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.begin() as connection:
        tables = inspect(connection).get_table_names()
        if "alembic_version" in tables:
            version = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if version != head:
                raise RuntimeError("SQLite schema version differs from this application; upgrade support is required.")
        elif tables:
            raise RuntimeError("SQLite database has an unrecognized schema; refusing to overwrite it.")
        else:
            Base.metadata.create_all(connection)
            connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            connection.execute(text("INSERT INTO alembic_version VALUES (:version)"), {"version": head})
        missing = set(Base.metadata.tables) - set(inspect(connection).get_table_names())
        if missing:
            raise RuntimeError("SQLite schema is incomplete: " + ", ".join(sorted(missing)))


if __name__ == "__main__":
    initialize_database()
    from .bootstrap import bootstrap
    bootstrap()
