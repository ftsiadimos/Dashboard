import os

from flask import current_app, render_template, send_from_directory

from dashboard.blueprints import bp as main
from dashboard.database import Application, Category, get_db
from dashboard.utils import get_settings


@main.route("/")
def index():
    settings = get_settings()
    with get_db() as db:
        categories = db.query(Category).order_by(Category.sort_order, Category.name).all()
        applications = db.query(Application).order_by(
            Application.pinned.desc(), Application.sort_order, Application.title
        ).all()
    return render_template(
        "index.html",
        categories=categories,
        applications=applications,
        settings=settings,
    )


@main.route("/about")
def about_page():
    settings = get_settings()
    # read version from file
    try:
        version_file = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "VERSION")
        )
        with open(version_file, "r") as f:
            version = f.read().strip()
    except Exception:
        version = "?"
    return render_template("about.html", settings=settings, version=version)


@main.route("/icons/<path:filename>")
def uploaded_icon(filename):
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    from werkzeug.utils import secure_filename

    safe_name = secure_filename(filename)
    return send_from_directory(upload_dir, safe_name)
