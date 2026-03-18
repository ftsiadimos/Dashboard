from flask import flash, redirect, render_template, request, url_for

from dashboard.blueprints import bp as main
from dashboard.database import Setting, get_db
from dashboard.utils import get_settings


@main.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        # we persist a handful of settings; boolean flags need special handling
        keys = ["title", "background_url", "search_provider", "search_enabled", "navbar_enabled"]
        with get_db() as db:
            for key in keys:
                if key in ("search_enabled", "navbar_enabled"):
                    # checkbox + hidden field means request.form.get will always return the
                    # first value we send ("false"), so normalize explicitly
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
