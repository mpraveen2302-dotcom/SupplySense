from sqlalchemy import create_engine
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

def get_engine():
    return engine

def get_table(name):
    return engine.execute(f"SELECT * FROM {name}")

def run_query(query, params=None):
    with engine.begin() as conn:
        conn.execute(query, params or {})
