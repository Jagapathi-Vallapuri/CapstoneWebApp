from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from core.config import settings
from typing import cast

# Create a robust SQLAlchemy engine suitable for cloud DBs (e.g., RDS)
# - pool_pre_ping avoids stale connection issues
# - pool_recycle helps with MySQL "server has gone away" on long idle
# - SQLite requires special connect args when used in dev
_engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,  # seconds
}

try:
    url = str(settings.DATABASE_URL)
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite"):
        _engine_kwargs["connect_args"] = {"check_same_thread": False}
except Exception:
    url = str(settings.DATABASE_URL)

engine = create_engine(cast(str, url), **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()