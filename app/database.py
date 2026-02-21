import os
from sqlalchemy import create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/supplysense"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def get_engine():
    return engine
