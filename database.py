import os
import sqlite3
from contextlib import contextmanager

from config import Config

DB_PATH = Config.SQLALCHEMY_DATABASE_URI.replace("sqlite:///", "")


def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    # always ensure tables are present; this avoids "no such table" errors
    # when the database file is missing or recreated.
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_tables(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_tables(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            icon TEXT DEFAULT '',
            color TEXT DEFAULT '#1a1a2e',
            description TEXT DEFAULT '',
            category_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            pinned INTEGER DEFAULT 0,
            api_url TEXT DEFAULT '',
            api_method TEXT DEFAULT 'GET',
            api_headers TEXT DEFAULT '',
            api_value_template TEXT DEFAULT '',
            api_interval INTEGER DEFAULT 30,
            api_payload TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    """)
    # Migrate: add API columns to existing tables
    cursor = db.execute("PRAGMA table_info(applications)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    migrations = [
        ("api_url", "TEXT DEFAULT ''"),
        ("api_method", "TEXT DEFAULT 'GET'"),
        ("api_headers", "TEXT DEFAULT ''"),
        ("api_value_template", "TEXT DEFAULT ''"),
        ("api_interval", "INTEGER DEFAULT 30"),
        ("api_payload", "TEXT DEFAULT ''"),  # body/payload for POST requests
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            current_app = None
            try:
                # import here to avoid circular import at module load
                from flask import current_app as _ca
                current_app = _ca
            except ImportError:
                pass
            msg = f"migrating applications table: adding column {col_name}"
            if current_app:
                current_app.logger.info(msg)
            else:
                print(msg)
            db.execute(f"ALTER TABLE applications ADD COLUMN {col_name} {col_def}")
    db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    # Insert default settings if none exist
    cursor = db.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        defaults = [
            ("title", "Dashboard"),
            ("background_url", ""),
            ("search_provider", "https://www.google.com/search?q="),
            ("search_enabled", "true"),
            ("columns", "6"),
        ]
        db.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", defaults
        )
    db.commit()


def init_db():
    with get_db() as db:
        pass  # _ensure_tables is called automatically by get_db()
