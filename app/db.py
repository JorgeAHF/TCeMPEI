from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def get_engine(url: str | None = None, echo: bool = False):
    return create_engine(url or DATABASE_URL, echo=echo, future=True)


def get_session_local(
    url: str | None = None, echo: bool = False, engine=None
):
    engine = engine or get_engine(url=url, echo=echo)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

