import os
from pathlib import Path

from flask import Flask

from .db import init_app as init_db_app
from .routes import bp


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "astronomy-local"),
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        CURRENT_LOCATION=os.environ.get("CURRENT_LOCATION", "Athens, TX"),
        LOCATIONS_FILE=os.environ.get(
            "LOCATIONS_FILE",
            str(Path(app.root_path).parent / "data" / "locations" / "locations.json"),
        ),
        IPGEOLOCATION_API_KEY=os.environ.get("IPGEOLOCATION_API_KEY", ""),
        NASA_API_KEY=os.environ.get("NASA_API_KEY", "DEMO_KEY"),
        ASTRONOMY_MEDIA_DIR=os.environ.get(
            "ASTRONOMY_MEDIA_DIR", "/app/static/media/astronomy"
        ),
    )
    if test_config:
        app.config.update(test_config)
    init_db_app(app)
    app.register_blueprint(bp)
    return app
