from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import config
from src.db.models import Base


def get_engine(database_url: str | None = None):
    url = database_url or config.DATABASE_URL
    return create_engine(url, future=True)


def init_db(engine):
    Base.metadata.create_all(engine)


def get_session(engine):
    session_factory = sessionmaker(bind=engine, future=True)
    return session_factory()
