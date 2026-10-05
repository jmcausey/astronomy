from flask import Flask
from .db import init_app as init_db_app
from .routes import bp

def create_app(test_config=None):
app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
    app.config.from_mapping(SECRET_KEY="change-this-secret",DATABASE_URL=None,CURRENT_LOCATION="Athens, TX",LOCATIONS_FILE="/app/data/locations/locations.json",IPGEOLOCATION_API_KEY=None,NASA_API_KEY="DEMO_KEY",ASTRONOMY_MEDIA_DIR="/app/static/media/astronomy")
    if test_config: app.config.update(test_config)
    init_db_app(app); app.register_blueprint(bp); return app
