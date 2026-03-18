from flask import Blueprint

# The blueprint is named "main" so that url_for("main.xxx") continues to work.
bp = Blueprint("main", __name__)
