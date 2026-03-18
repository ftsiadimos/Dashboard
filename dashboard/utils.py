import os
import uuid

from flask import current_app

from dashboard.database import get_db, Setting

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_settings() -> dict[str, str]:
    with get_db() as db:
        return {s.key: s.value for s in db.query(Setting).all()}


def save_uploaded_icon(file) -> str:
    """Save uploaded icon file and return the filename."""
    ext = file.filename.rsplit(".", 1)[1].lower()
    icon_filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, icon_filename))
    return icon_filename
