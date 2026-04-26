import io
import os
import uuid
from urllib.parse import urlparse

import requests
from PIL import Image

from flask import current_app

from dashboard.database import get_db, Setting

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico"}

ICON_SIZE = (64, 64)
ICON_FORMAT = "PNG"
ICON_EXT = "png"


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_settings() -> dict[str, str]:
    with get_db() as db:
        return {s.key: s.value for s in db.query(Setting).all()}


def _process_and_save_image(img: Image.Image, upload_dir: str) -> str:
    """Resize image to ICON_SIZE, convert to ICON_FORMAT, save, and return filename."""
    img = img.convert("RGBA")
    img.thumbnail(ICON_SIZE, Image.LANCZOS)
    # Paste onto a square canvas so dimensions are exactly ICON_SIZE
    canvas = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
    offset = ((ICON_SIZE[0] - img.width) // 2, (ICON_SIZE[1] - img.height) // 2)
    canvas.paste(img, offset)
    icon_filename = f"{uuid.uuid4().hex}.{ICON_EXT}"
    os.makedirs(upload_dir, exist_ok=True)
    canvas.save(os.path.join(upload_dir, icon_filename), format=ICON_FORMAT)
    return icon_filename


def save_uploaded_icon(file) -> str:
    """Save uploaded icon file and return the filename."""
    ext = file.filename.rsplit(".", 1)[1].lower()
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    # SVG files are not raster images – store as-is
    if ext == "svg":
        icon_filename = f"{uuid.uuid4().hex}.svg"
        file.save(os.path.join(upload_dir, icon_filename))
        return icon_filename
    img = Image.open(file.stream)
    return _process_and_save_image(img, upload_dir)


def save_icon_from_url(url: str) -> str:
    """Download an icon from *url*, resize + convert it, and return the filename.

    Raises ValueError for invalid/unsafe URLs and requests.RequestException on
    network errors.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Icon URL must use http or https.")

    response = requests.get(url, timeout=10, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"URL did not return an image (Content-Type: {content_type}).")

    img = Image.open(io.BytesIO(response.content))
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return _process_and_save_image(img, upload_dir)
