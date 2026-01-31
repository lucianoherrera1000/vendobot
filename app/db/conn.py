import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    # .../Vendobot/app/db/conn.py -> parents[2] = .../Vendobot
    base = Path(__file__).resolve().parents[2]
    return base / "vendobot.sqlite3"


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    conn = get_connection()
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
