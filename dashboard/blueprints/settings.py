import json

from flask import flash, redirect, render_template, request, url_for, jsonify

from dashboard.blueprints import bp as main
from dashboard.database import Application, Category, Setting, get_db
from dashboard.utils import get_settings


@main.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        section = request.form.get("form_section", "dashboard")

        section_keys = {
            "dashboard": ["title", "background_url", "search_provider",
                          "search_enabled", "navbar_enabled", "alert_keywords"],
            "terminal":  ["terminal_key", "terminal_height", "terminal_opacity",
                          "terminal_font_size", "terminal_font_family",
                          "terminal_accent", "terminal_anim_speed"],
            "ollama":    ["ollama_url", "ollama_model", "ollama_system_prompt"],
        }
        keys = section_keys.get(section, list(section_keys["dashboard"]))
        bool_keys = {"search_enabled", "navbar_enabled"}

        with get_db() as db:
            for key in keys:
                if key in bool_keys:
                    value = "true" if request.form.get(key) == "true" else "false"
                else:
                    value = request.form.get(key, "").strip()
                setting = db.get(Setting, key)
                if setting:
                    setting.value = value
                else:
                    db.add(Setting(key=key, value=value))
        flash("Settings saved.", "success")
        return redirect(url_for("main.settings_page"))
    settings = get_settings()
    return render_template("settings.html", settings=settings)


@main.route("/settings/export-apps")
def export_apps():
    with get_db() as db:
        categories = db.query(Category).order_by(Category.sort_order, Category.name).all()
        apps = db.query(Application).order_by(Application.sort_order, Application.title).all()

    data = {
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "sort_order": c.sort_order,
            }
            for c in categories
        ],
        "applications": [
            {
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "icon": a.icon,
                "color": a.color,
                "description": a.description,
                "category": a.category.name if a.category else None,
                "sort_order": a.sort_order,
                "pinned": a.pinned,
                "api_url": a.api_url,
                "api_method": a.api_method,
                "api_headers": a.api_headers,
                "api_payload": a.api_payload,
                "api_value_template": a.api_value_template,
                "api_interval": a.api_interval,
            }
            for a in apps
        ],
    }

    response = jsonify(data)
    response.headers["Content-Disposition"] = "attachment; filename=dashboard-apps-export.json"
    return response


@main.route("/settings/import-apps", methods=["POST"])
def import_apps():
    raw_json = None
    if "import_file" in request.files and request.files["import_file"].filename:
        raw_json = request.files["import_file"].read().decode("utf-8")
    else:
        raw_json = request.form.get("import_json", "").strip()

    if not raw_json:
        flash("No JSON provided for import.", "error")
        return redirect(url_for("main.settings_page"))

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        flash("Invalid JSON provided for import.", "error")
        return redirect(url_for("main.settings_page"))

    imported_apps = 0
    with get_db() as db:
        category_map = {c.name: c for c in db.query(Category).all()}

        for cat_data in payload.get("categories", []):
            name = cat_data.get("name")
            if not name:
                continue
            category = category_map.get(name)
            if category:
                category.sort_order = cat_data.get("sort_order", category.sort_order)
            else:
                category = Category(name=name, sort_order=cat_data.get("sort_order", 0))
                db.add(category)
            category_map[name] = category

        for app_data in payload.get("applications", []):
            title = (app_data.get("title") or "").strip()
            url = (app_data.get("url") or "").strip()
            if not title or not url:
                continue

            existing = db.query(Application).filter_by(title=title).first()
            if existing:
                app = existing
            else:
                app = Application(title=title, url=url)
                db.add(app)

            app.url = url
            app.icon = app_data.get("icon", "") or ""
            app.color = app_data.get("color", "#1a1a2e") or "#1a1a2e"
            app.description = app_data.get("description", "") or ""
            app.sort_order = app_data.get("sort_order", 0) or 0
            app.pinned = app_data.get("pinned", 0) or 0
            app.api_url = app_data.get("api_url", "") or ""
            app.api_method = app_data.get("api_method", "GET") or "GET"
            app.api_headers = app_data.get("api_headers", "") or ""
            app.api_payload = app_data.get("api_payload", "") or ""
            app.api_value_template = app_data.get("api_value_template", "") or ""
            app.api_interval = int(app_data.get("api_interval", 30) or 30)

            category_name = app_data.get("category")
            if category_name:
                category = category_map.get(category_name)
                app.category_id = category.id if category else None
            else:
                app.category_id = None

            imported_apps += 1

    flash(f"Imported {imported_apps} applications.", "success")
    return redirect(url_for("main.settings_page"))
