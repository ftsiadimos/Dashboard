import json
import os
import uuid

import requests as http_requests
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from database import get_db

main = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_settings():
    with get_db() as db:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


# ── Dashboard ────────────────────────────────────────────────────────────────


@main.route("/")
def index():
    settings = get_settings()
    with get_db() as db:
        categories = db.execute(
            "SELECT * FROM categories ORDER BY sort_order, name"
        ).fetchall()
        applications = db.execute(
            "SELECT * FROM applications ORDER BY pinned DESC, sort_order, title"
        ).fetchall()
    return render_template(
        "index.html",
        categories=categories,
        applications=applications,
        settings=settings,
    )


# ── Applications CRUD ────────────────────────────────────────────────────────


@main.route("/apps")
def apps_list():
    settings = get_settings()
    with get_db() as db:
        apps = db.execute(
            "SELECT a.*, c.name as category_name FROM applications a "
            "LEFT JOIN categories c ON a.category_id = c.id "
            "ORDER BY a.sort_order, a.title"
        ).fetchall()
        categories = db.execute(
            "SELECT * FROM categories ORDER BY sort_order, name"
        ).fetchall()
    return render_template(
        "apps.html", apps=apps, categories=categories, settings=settings
    )


@main.route("/apps/add", methods=["GET", "POST"])
def app_add():
    settings = get_settings()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        url_val = request.form.get("url", "").strip()
        color = request.form.get("color", "#1a1a2e").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id") or None
        pinned = 1 if request.form.get("pinned") else 0

        if not title or not url_val:
            flash("Title and URL are required.", "error")
            with get_db() as db:
                categories = db.execute(
                    "SELECT * FROM categories ORDER BY name"
                ).fetchall()
            return render_template(
                "app_form.html", categories=categories, settings=settings
            )

        icon_filename = ""
        if "icon" in request.files:
            file = request.files["icon"]
            if file and file.filename and allowed_file(file.filename):
                ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
                icon_filename = f"{uuid.uuid4().hex}.{ext}"
                upload_dir = current_app.config["UPLOAD_FOLDER"]
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, icon_filename))

        api_url = request.form.get("api_url", "").strip()
        api_method = request.form.get("api_method", "GET").strip()
        api_headers = request.form.get("api_headers", "").strip()
        api_payload = request.form.get("api_payload", "").strip()
        api_value_template = request.form.get("api_value_template", "").strip()
        api_interval = int(request.form.get("api_interval", 30) or 30)

        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO applications (title, url, icon, color, description, category_id, pinned, "
                    "api_url, api_method, api_headers, api_payload, api_value_template, api_interval) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (title, url_val, icon_filename, color, description, category_id, pinned,
                     api_url, api_method, api_headers, api_payload, api_value_template, api_interval),
                )
            flash("Application added successfully.", "success")
            return redirect(url_for("main.apps_list"))
        except Exception as exc:  # catch sqlite3.OperationalError or others
            current_app.logger.exception("error inserting new application")
            flash(f"Database error: {exc}", "error")
            with get_db() as db:
                categories = db.execute(
                    "SELECT * FROM categories ORDER BY name"
                ).fetchall()
            return render_template(
                "app_form.html", categories=categories, settings=settings
            )

    with get_db() as db:
        categories = db.execute(
            "SELECT * FROM categories ORDER BY name"
        ).fetchall()
    return render_template(
        "app_form.html", categories=categories, settings=settings
    )


@main.route("/apps/<int:app_id>/edit", methods=["GET", "POST"])
def app_edit(app_id):
    settings = get_settings()
    with get_db() as db:
        app = db.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()

    if not app:
        flash("Application not found.", "error")
        return redirect(url_for("main.apps_list"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        url_val = request.form.get("url", "").strip()
        color = request.form.get("color", "#1a1a2e").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id") or None
        pinned = 1 if request.form.get("pinned") else 0

        if not title or not url_val:
            flash("Title and URL are required.", "error")
            with get_db() as db:
                categories = db.execute(
                    "SELECT * FROM categories ORDER BY name"
                ).fetchall()
            return render_template(
                "app_form.html", app=app, categories=categories, settings=settings
            )

        icon_filename = app["icon"]
        if "icon" in request.files:
            file = request.files["icon"]
            if file and file.filename and allowed_file(file.filename):
                # Remove old icon
                if app["icon"]:
                    old_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"], app["icon"]
                    )
                    if os.path.exists(old_path):
                        os.remove(old_path)
                ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
                icon_filename = f"{uuid.uuid4().hex}.{ext}"
                upload_dir = current_app.config["UPLOAD_FOLDER"]
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, icon_filename))

        api_url = request.form.get("api_url", "").strip()
        api_method = request.form.get("api_method", "GET").strip()
        api_headers = request.form.get("api_headers", "").strip()
        api_payload = request.form.get("api_payload", "").strip()
        api_value_template = request.form.get("api_value_template", "").strip()
        api_interval = int(request.form.get("api_interval", 30) or 30)

        try:
            with get_db() as db:
                db.execute(
                    "UPDATE applications SET title=?, url=?, icon=?, color=?, "
                    "description=?, category_id=?, pinned=?, "
                    "api_url=?, api_method=?, api_headers=?, api_payload=?, api_value_template=?, api_interval=? "
                    "WHERE id=?",
                    (title, url_val, icon_filename, color, description, category_id, pinned,
                     api_url, api_method, api_headers, api_payload, api_value_template, api_interval, app_id),
                )
            flash("Application updated successfully.", "success")
            return redirect(url_for("main.apps_list"))
        except Exception as exc:
            current_app.logger.exception("error updating application %s", app_id)
            flash(f"Database error: {exc}", "error")
            with get_db() as db:
                categories = db.execute(
                    "SELECT * FROM categories ORDER BY name"
                ).fetchall()
            return render_template(
                "app_form.html", app=app, categories=categories, settings=settings
            )

    with get_db() as db:
        categories = db.execute(
            "SELECT * FROM categories ORDER BY name"
        ).fetchall()
    return render_template(
        "app_form.html", app=app, categories=categories, settings=settings
    )


@main.route("/apps/<int:app_id>/delete", methods=["POST"])
def app_delete(app_id):
    with get_db() as db:
        app = db.execute(
            "SELECT icon FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        if app and app["icon"]:
            icon_path = os.path.join(current_app.config["UPLOAD_FOLDER"], app["icon"])
            if os.path.exists(icon_path):
                os.remove(icon_path)
        db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    flash("Application deleted.", "success")
    return redirect(url_for("main.apps_list"))


# ── Categories CRUD ──────────────────────────────────────────────────────────


@main.route("/categories")
def categories_list():
    settings = get_settings()
    with get_db() as db:
        categories = db.execute(
            "SELECT c.*, COUNT(a.id) as app_count FROM categories c "
            "LEFT JOIN applications a ON a.category_id = c.id "
            "GROUP BY c.id ORDER BY c.sort_order, c.name"
        ).fetchall()
    return render_template(
        "categories.html", categories=categories, settings=settings
    )


@main.route("/categories/add", methods=["GET", "POST"])
def category_add():
    settings = get_settings()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "error")
            return render_template("category_form.html", settings=settings)
        with get_db() as db:
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        flash("Category added.", "success")
        return redirect(url_for("main.categories_list"))
    return render_template("category_form.html", settings=settings)


@main.route("/categories/<int:cat_id>/edit", methods=["GET", "POST"])
def category_edit(cat_id):
    settings = get_settings()
    with get_db() as db:
        cat = db.execute(
            "SELECT * FROM categories WHERE id = ?", (cat_id,)
        ).fetchone()
    if not cat:
        flash("Category not found.", "error")
        return redirect(url_for("main.categories_list"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "error")
            return render_template(
                "category_form.html", category=cat, settings=settings
            )
        with get_db() as db:
            db.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
        flash("Category updated.", "success")
        return redirect(url_for("main.categories_list"))
    return render_template("category_form.html", category=cat, settings=settings)


@main.route("/categories/<int:cat_id>/delete", methods=["POST"])
def category_delete(cat_id):
    with get_db() as db:
        db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    flash("Category deleted.", "success")
    return redirect(url_for("main.categories_list"))


# ── Settings ─────────────────────────────────────────────────────────────────


@main.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        keys = ["title", "background_url", "search_provider", "search_enabled", "columns"]
        with get_db() as db:
            for key in keys:
                value = request.form.get(key, "").strip()
                db.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
        flash("Settings saved.", "success")
        return redirect(url_for("main.settings_page"))
    settings = get_settings()
    return render_template("settings.html", settings=settings)


@main.route("/about")
def about_page():
    settings = get_settings()
    # read version from file
    try:
        with open(os.path.join(os.path.dirname(__file__), "VERSION"), "r") as f:
            version = f.read().strip()
    except Exception:
        version = "?"
    return render_template("about.html", settings=settings, version=version)


# ── API for drag-and-drop reorder ────────────────────────────────────────────


@main.route("/api/reorder", methods=["POST"])
def api_reorder():
    data = request.get_json()
    if not data or "items" not in data or "type" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    table = "applications" if data["type"] == "app" else "categories"
    if table not in ("applications", "categories"):
        return jsonify({"error": "Invalid type"}), 400

    with get_db() as db:
        for i, item_id in enumerate(data["items"]):
            if not isinstance(item_id, int):
                continue
            db.execute(
                f"UPDATE {table} SET sort_order = ? WHERE id = ?", (i, item_id)
            )
    return jsonify({"status": "ok"})


# ── API proxy for app stats ──────────────────────────────────────────────────


def _extract_value(data, template):
    """Extract value(s) from JSON data using a template.

    Template syntax:
      - Simple JSONPath-like: ``status``, ``data.count``, ``info.version``
      - Multiple fields:  ``Status: {status} | Users: {data.users.total}``
    """
    def _resolve(obj, path):
        for key in path.split("."):
            if key == "_len" and isinstance(obj, list):
                return len(obj)
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list):
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return obj

    if not template:
        # No template — return a compact summary
        if isinstance(data, list):
            return f"{len(data)} items"
        if isinstance(data, dict):
            parts = []
            for k, v in list(data.items())[:4]:
                parts.append(f"{k}: {v}" if not isinstance(v, (dict, list)) else f"{k}: ...")
            return " | ".join(parts)
        return str(data)[:120]



    # if template begins with "regex:", treat data as plain text and apply pattern
    if isinstance(data, str) and isinstance(template, str) and template.startswith("regex:"):
        import re
        pattern = template[len("regex:"):]
        m = re.search(pattern, data, re.S)
        if m:
            return m.group(1)
        return "—"

    if "{" in template:
        import re
        def replacer(m):
            val = _resolve(data, m.group(1))
            return str(val) if val is not None else "—"
        return re.sub(r"\{([^}]+)\}", replacer, template)

    val = _resolve(data, template)
    return str(val) if val is not None else "—"





def _npm_get_hosts(base_url: str, identity: str, secret: str, verify: bool = True):
    """Authenticate with NPM and return /api/nginx/proxy-hosts JSON."""
    sess = http_requests.Session()
    if not verify:
        sess.verify = False

    auth = sess.post(base_url + "api/tokens",
                     json={"identity": identity, "secret": secret},
                     headers={"Accept": "application/json"})
    auth.raise_for_status()
    token = auth.json().get("token")
    if not token:
        raise ValueError("failed to obtain NPM token")

    res = sess.get(base_url + "api/nginx/proxy-hosts",
                   headers={"Accept": "application/json",
                            "Authorization": f"Bearer {token}"})
    res.raise_for_status()
    return res.json()


@main.route("/api/app/<int:app_id>/stats")
def api_app_stats(app_id):
    with get_db() as db:
        app = db.execute(
            "SELECT api_url, api_method, api_headers, api_payload, api_value_template "
            "FROM applications WHERE id = ?", (app_id,)
        ).fetchone()

    if not app or not app["api_url"]:
        return jsonify({"error": "No API configured"}), 404

    headers = {}
    if app["api_headers"]:
        try:
            headers = json.loads(app["api_headers"])
            if not isinstance(headers, dict):
                headers = {}
        except (json.JSONDecodeError, TypeError):
            headers = {}

    try:
        method = app["api_method"].upper() if app["api_method"] else "GET"
        # prepare request kwargs; include payload if provided for non-GET methods
        kwargs = {"headers": headers, "timeout": 10, "verify": True}
        payload_val = app["api_payload"] if "api_payload" in app.keys() else None
        # special-case Nginx Proxy Manager: perform login flow if creds provided
        if app["api_url"].endswith("/api/nginx/proxy-hosts") and payload_val:
            try:
                creds = json.loads(payload_val)
            except Exception:
                creds = {}
            # support both identity/secret and email/password naming
            if isinstance(creds, dict) and (
                ("identity" in creds and "secret" in creds) or
                ("email" in creds and "password" in creds)
            ):
                ident = creds.get("identity") or creds.get("email")
                secret = creds.get("secret") or creds.get("password")
                verify = not creds.get("ignore_tls", False)
                data = _npm_get_hosts(
                    app["api_url"].rsplit("/api/nginx/proxy-hosts", 1)[0] + "/",
                    ident,
                    secret,
                    verify,
                )
                display = _extract_value(data, app["api_value_template"])
                return jsonify({"ok": True, "display": display})
        if payload_val and method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                kwargs["json"] = json.loads(payload_val)
            except Exception:
                kwargs["data"] = payload_val
        resp = http_requests.request(method, app["api_url"], **kwargs)

        # LOGGING: dump status and body if not OK
        if not resp.ok:
            current_app.logger.warning(
                "API call to %s returned %s:\n%s",
                app["api_url"],
                resp.status_code,
                resp.text,
            )

        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            # response isn't JSON – keep full text so regex templates work
            data = resp.text

        display = _extract_value(data, app["api_value_template"])
        return jsonify({"ok": True, "display": display})

    except http_requests.RequestException as exc:
        return jsonify({"ok": False, "display": f"Error: {exc.__class__.__name__}"})


# ── Uploaded icons ───────────────────────────────────────────────────────────


@main.route("/icons/<path:filename>")
def uploaded_icon(filename):
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    safe_name = secure_filename(filename)
    return send_from_directory(upload_dir, safe_name)
