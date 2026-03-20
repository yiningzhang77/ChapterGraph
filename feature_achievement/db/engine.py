from sqlmodel import SQLModel, Session, create_engine

from feature_achievement.runtime_config import get_database_url

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
