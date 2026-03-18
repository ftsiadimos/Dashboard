from contextlib import contextmanager

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, text
from sqlalchemy.engine import Engine
from sqlite3 import Connection as SQLite3Connection

# -----------------------------------------------------------
# SQLAlchemy setup
# -----------------------------------------------------------
db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())

    applications = db.relationship(
        "Application",
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    icon = db.Column(db.Text, default="")
    color = db.Column(db.Text, default="#1a1a2e")
    description = db.Column(db.Text, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    pinned = db.Column(db.Integer, default=0)

    api_url = db.Column(db.Text, default="")
    api_method = db.Column(db.Text, default="GET")
    api_headers = db.Column(db.Text, default="")
    api_value_template = db.Column(db.Text, default="")
    api_interval = db.Column(db.Integer, default=30)
    api_payload = db.Column(db.Text, default="")

    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())

    category = db.relationship("Category", back_populates="applications")

    @property
    def category_name(self):
        return self.category.name if self.category else None


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.Text, primary_key=True)
    value = db.Column(db.Text, nullable=False)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    # Ensure WAL mode + foreign key support for sqlite
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ensure_default_settings(session):
    # Insert default settings only if they do not exist
    existing = {s.key for s in session.query(Setting.key).all()}
    defaults = {
        "title": "Dashboard",
        "background_url": "",
        "search_provider": "https://www.google.com/search?q=",
        "search_enabled": "true",
        "navbar_enabled": "true",
        "columns": "4",
    }
    for key, value in defaults.items():
        if key not in existing:
            session.add(Setting(key=key, value=value))


def _migrate_applications_table(engine):
    # Keeps legacy sqlite DB schema compatible with new ORM model (adds missing columns)
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(applications)"))
        existing_cols = {row[1] for row in result.fetchall()}

        migrations = [
            ("api_url", "TEXT DEFAULT ''"),
            ("api_method", "TEXT DEFAULT 'GET'"),
            ("api_headers", "TEXT DEFAULT ''"),
            ("api_value_template", "TEXT DEFAULT ''"),
            ("api_interval", "INTEGER DEFAULT 30"),
            ("api_payload", "TEXT DEFAULT ''"),
        ]

        for col_name, col_def in migrations:
            if col_name not in existing_cols:
                conn.execute(text(f"ALTER TABLE applications ADD COLUMN {col_name} {col_def}"))


def init_db(app):
    """Initialize SQLAlchemy and create/migrate tables."""
    db.init_app(app)

    # Ensure objects remain usable after commit so views can safely read attributes
    # after the session context closes.
    db.session.expire_on_commit = False

    with app.app_context():
        # Create any missing tables
        db.create_all()
        # Migrate schema for legacy sqlite DBs where ALTER may be needed
        _migrate_applications_table(db.engine)
        # Ensure default settings exist
        with get_db() as session:
            _ensure_default_settings(session)


@contextmanager
def get_db():
    """Context manager that yields a SQLAlchemy session with commit/rollback.

    The session is not closed here because Flask-SQLAlchemy manages session
    lifecycle at the end of each request. Closing it early causes instances to
    detach and makes template rendering fail.
    """
    session = db.session
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
