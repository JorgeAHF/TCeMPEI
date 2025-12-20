from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def get_engine(url: str | None = None, echo: bool = False):
    return create_engine(url or DATABASE_URL, echo=echo, future=True)


def get_session_local(url: str | None = None, echo: bool = False):
    engine = get_engine(url=url, echo=echo)
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

