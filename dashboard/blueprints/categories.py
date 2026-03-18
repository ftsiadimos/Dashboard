from flask import flash, redirect, render_template, request, url_for

from sqlalchemy import func

from dashboard.blueprints import bp as main
from dashboard.database import Application, Category, get_db
from dashboard.utils import get_settings


@main.route("/categories")
def categories_list():
    settings = get_settings()
    with get_db() as db:
        rows = (
            db.query(Category, func.count(Application.id).label("app_count"))
            .outerjoin(Application)
            .group_by(Category.id)
            .order_by(Category.sort_order, Category.name)
            .all()
        )
        categories = []
        for cat, count in rows:
            cat.app_count = count
            categories.append(cat)
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
            db.add(Category(name=name))
        flash("Category added.", "success")
        return redirect(url_for("main.categories_list"))
    return render_template("category_form.html", settings=settings)


@main.route("/categories/<int:cat_id>/edit", methods=["GET", "POST"])
def category_edit(cat_id):
    settings = get_settings()
    with get_db() as db:
        cat = db.get(Category, cat_id)
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
            cat.name = name
        flash("Category updated.", "success")
        return redirect(url_for("main.categories_list"))
    return render_template("category_form.html", category=cat, settings=settings)


@main.route("/categories/<int:cat_id>/delete", methods=["POST"])
def category_delete(cat_id):
    with get_db() as db:
        cat = db.get(Category, cat_id)
        if cat:
            db.delete(cat)
    flash("Category deleted.", "success")
    return redirect(url_for("main.categories_list"))
