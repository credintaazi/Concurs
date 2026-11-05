from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


url = make_url(settings.db_url)
is_sqlite = url.get_backend_name() == "sqlite"
if is_sqlite and url.database and url.database != ":memory:":
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(url, pool_pre_ping=True,
                       **({"connect_args": {"check_same_thread": False, "timeout": 30}} if is_sqlite else {}))
if is_sqlite:
    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA journal_mode=WAL")

    @event.listens_for(engine, "begin")
    def begin_sqlite(connection):
        # SQLite ignores SELECT FOR UPDATE. Reserve the writer before any reads
        # so authentication + edition checks + writes form one serialized snapshot.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
