import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'data', 'dashboard.db')}"
    )
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "data", "icons")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB max upload
    APP_TITLE = os.environ.get("APP_TITLE", "Dashboard")
    APP_PORT = int(os.environ.get("APP_PORT", 6008))  # default changed to 6008
    APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
