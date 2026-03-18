from flask import Flask

from dashboard.config import Config
from dashboard.database import init_db


def create_app():
    import os

    template_folder = os.path.join(os.path.dirname(__file__), "..", "templates")
    static_folder = os.path.join(os.path.dirname(__file__), "..", "static")

    app = Flask(
        __name__,
        template_folder=os.path.abspath(template_folder),
        static_folder=os.path.abspath(static_folder),
    )
    app.config.from_object(Config)

    # Ensure upload folder exists
    import os

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize database (creates/migrates tables)
    init_db(app)

    # Import modules that register routes on the blueprint
    import dashboard.blueprints.main  # noqa: F401
    import dashboard.blueprints.apps  # noqa: F401
    import dashboard.blueprints.categories  # noqa: F401
    import dashboard.blueprints.settings  # noqa: F401
    import dashboard.blueprints.api  # noqa: F401

    # Register the single shared blueprint
    from dashboard.blueprints import bp

    app.register_blueprint(bp)

    return app
