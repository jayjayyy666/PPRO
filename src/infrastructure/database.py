import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./drevenka.db")

# SQLAlchemy 2.1+ defaultně používá psycopg (v3) pro PostgreSQL.
# Explicitně přepíšeme na psycopg2, který máme nainstalovaný (psycopg2-binary).
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Závislost pro FastAPI endpointy (generátor DB session)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Inicializace databázových tabulek."""
    import src.infrastructure.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
