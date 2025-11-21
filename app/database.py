from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
#from pathlib import Path

#BASE_DIR = Path(__file__).resolve().parent.parent
#DB_PATH = BASE_DIR / "database.db"

DATABASE_URL = "postgresql+psycopg2://taskengine:taskengine@localhost:5432/taskengine"

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
