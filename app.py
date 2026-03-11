import os

from flask import Flask

from config import Config
from database import init_db
from routes import main


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    with app.app_context():
        init_db()

    app.register_blueprint(main)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=Config.APP_HOST, port=Config.APP_PORT, debug=True)  # default port now 6008
