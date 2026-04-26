import os

from flask import current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from dashboard.blueprints import bp as main
from dashboard.database import Application, Category, get_db
from dashboard.utils import allowed_file, get_settings, save_icon_from_url, save_uploaded_icon


@main.route("/apps")
def apps_list():
    settings = get_settings()
    with get_db() as db:
        apps = (
            db.query(Application)
            .options(joinedload(Application.category))
            .outerjoin(Category)
            .order_by(
                Application.pinned.desc(),
                Category.sort_order,
                Category.name,
                Application.title,
            )
            .all()
        )
        categories = db.query(Category).order_by(Category.sort_order, Category.name).all()
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
                categories = db.query(Category).order_by(Category.name).all()
            return render_template(
                "app_form.html", categories=categories, settings=settings
            )

        icon_filename = ""
        icon_url = request.form.get("icon_url", "").strip()
        if "icon" in request.files:
            file = request.files["icon"]
            if file and file.filename and allowed_file(file.filename):
                icon_filename = save_uploaded_icon(file)
        if not icon_filename and icon_url:
            try:
                icon_filename = save_icon_from_url(icon_url)
            except Exception as exc:
                flash(f"Could not download icon from URL: {exc}", "error")

        api_url = request.form.get("api_url", "").strip()
        api_method = request.form.get("api_method", "GET").strip()
        api_headers = request.form.get("api_headers", "").strip()
        api_payload = request.form.get("api_payload", "").strip()
        api_value_template = request.form.get("api_value_template", "").strip()
        api_interval = int(request.form.get("api_interval", 30) or 30)
        api_verify = bool(request.form.get("api_verify"))

        try:
            with get_db() as db:
                app = Application(
                    title=title,
                    url=url_val,
                    icon=icon_filename,
                    color=color,
                    description=description,
                    category_id=category_id,
                    pinned=pinned,
                    api_url=api_url,
                    api_method=api_method,
                    api_headers=api_headers,
                    api_payload=api_payload,
                    api_value_template=api_value_template,
                    api_interval=api_interval,
                    api_verify=api_verify,
                )
                db.add(app)
            flash("Application added successfully.", "success")
            return redirect(url_for("main.apps_list"))
        except Exception as exc:  # catch sqlite3.OperationalError or others
            current_app.logger.exception("error inserting new application")
            flash(f"Database error: {exc}", "error")
            with get_db() as db:
                categories = db.query(Category).order_by(Category.name).all()
            return render_template(
                "app_form.html", categories=categories, settings=settings
            )

    with get_db() as db:
        categories = db.query(Category).order_by(Category.name).all()
    return render_template(
        "app_form.html", categories=categories, settings=settings
    )


@main.route("/apps/<int:app_id>/edit", methods=["GET", "POST"])
def app_edit(app_id):
    settings = get_settings()
    with get_db() as db:
        app = db.get(Application, app_id)

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
                categories = db.query(Category).order_by(Category.name).all()
            return render_template(
                "app_form.html", app=app, categories=categories, settings=settings
            )

        icon_filename = app.icon
        icon_url = request.form.get("icon_url", "").strip()
        if "icon" in request.files:
            file = request.files["icon"]
            if file and file.filename and allowed_file(file.filename):
                # Remove old icon
                if app.icon:
                    old_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"], app.icon
                    )
                    if os.path.exists(old_path):
                        os.remove(old_path)
                icon_filename = save_uploaded_icon(file)
        if icon_url and icon_filename == app.icon:  # URL given, no file replaced it
            try:
                new_icon = save_icon_from_url(icon_url)
                if app.icon:
                    old_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"], app.icon
                    )
                    if os.path.exists(old_path):
                        os.remove(old_path)
                icon_filename = new_icon
            except Exception as exc:
                flash(f"Could not download icon from URL: {exc}", "error")

        api_url = request.form.get("api_url", "").strip()
        api_method = request.form.get("api_method", "GET").strip()
        api_headers = request.form.get("api_headers", "").strip()
        api_payload = request.form.get("api_payload", "").strip()
        api_value_template = request.form.get("api_value_template", "").strip()
        api_interval = int(request.form.get("api_interval", 30) or 30)
        api_verify = bool(request.form.get("api_verify"))

        try:
            with get_db() as db:
                app.title = title
                app.url = url_val
                app.icon = icon_filename
                app.color = color
                app.description = description
                app.category_id = category_id
                app.pinned = pinned
                app.api_url = api_url
                app.api_method = api_method
                app.api_headers = api_headers
                app.api_payload = api_payload
                app.api_value_template = api_value_template
                app.api_interval = api_interval
                app.api_verify = api_verify
            flash("Application updated successfully.", "success")
            return redirect(url_for("main.apps_list"))
        except Exception as exc:
            current_app.logger.exception("error updating application %s", app_id)
            flash(f"Database error: {exc}", "error")
            with get_db() as db:
                categories = db.query(Category).order_by(Category.name).all()
            return render_template(
                "app_form.html", app=app, categories=categories, settings=settings
            )

    with get_db() as db:
        categories = db.query(Category).order_by(Category.name).all()
    return render_template(
        "app_form.html", app=app, categories=categories, settings=settings
    )


@main.route("/apps/<int:app_id>/delete", methods=["POST"])
def app_delete(app_id):
    with get_db() as db:
        app = db.get(Application, app_id)
        if app and app.icon:
            icon_path = os.path.join(current_app.config["UPLOAD_FOLDER"], app.icon)
            if os.path.exists(icon_path):
                os.remove(icon_path)
        if app:
            db.delete(app)
    flash("Application deleted.", "success")
    return redirect(url_for("main.apps_list"))


@main.route("/apps/bulk", methods=["POST"])
def apps_bulk_update():
    """Bulk-update a set of applications (category assignment)."""
    app_ids = request.form.getlist("app_ids")
    category_id = request.form.get("category_id") or None

    if not app_ids:
        flash("No applications selected.", "error")
        return redirect(url_for("main.apps_list"))

    # Convert IDs to ints, ignoring invalid values.
    try:
        app_ids = [int(i) for i in app_ids]
    except ValueError:
        flash("Invalid application selection.", "error")
        return redirect(url_for("main.apps_list"))

    # Allow unsetting the category by passing blank.
    if category_id == "":
        category_id = None
    else:
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            category_id = None

    with get_db() as db:
        apps = db.query(Application).filter(Application.id.in_(app_ids)).all()
        for app in apps:
            app.category_id = category_id

    flash(f"Updated category for {len(apps)} application(s).", "success")
    return redirect(url_for("main.apps_list"))
