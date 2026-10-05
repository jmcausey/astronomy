import psycopg
from psycopg.rows import dict_row
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS astronomy (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    location TEXT,
    country_name TEXT,
    state_prov TEXT,
    city TEXT,
    locality TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    elevation DOUBLE PRECISION,
    mid_night TEXT,
    night_end TEXT,
    morn_astronomical_twilight_begin TEXT,
    morn_astronomical_twilight_end TEXT,
    morn_nautical_twilight_begin TEXT,
    morn_nautical_twilight_end TEXT,
    morn_civil_twilight_begin TEXT,
    morn_civil_twilight_end TEXT,
    morn_blue_hour_begin TEXT,
    morn_blue_hour_end TEXT,
    morn_golden_hour_begin TEXT,
    morn_golden_hour_end TEXT,
    sunrise TEXT,
    sunset TEXT,
    eve_golden_hour_begin TEXT,
    eve_golden_hour_end TEXT,
    eve_blue_hour_begin TEXT,
    eve_blue_hour_end TEXT,
    eve_civil_twilight_begin TEXT,
    eve_civil_twilight_end TEXT,
    eve_nautical_twilight_begin TEXT,
    eve_nautical_twilight_end TEXT,
    eve_astronomical_twilight_begin TEXT,
    eve_astronomical_twilight_end TEXT,
    night_begin TEXT,
    sun_status TEXT,
    solar_noon TEXT,
    day_length TEXT,
    sun_altitude DOUBLE PRECISION,
    sun_distance DOUBLE PRECISION,
    sun_azimuth DOUBLE PRECISION,
    moon_phase TEXT,
    moonrise TEXT,
    moonset TEXT,
    moon_status TEXT,
    moon_altitude DOUBLE PRECISION,
    moon_distance DOUBLE PRECISION,
    moon_azimuth DOUBLE PRECISION,
    moon_parallactic_angle DOUBLE PRECISION,
    moon_illumination_percentage DOUBLE PRECISION,
    moon_angle DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS astronomy_jobs (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    interval_minutes INTEGER NOT NULL CHECK (interval_minutes IN (15, 60, 240, 1440)),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMP,
    last_status TEXT,
    last_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_astronomy_timestamp
    ON astronomy(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_astronomy_location_timestamp
    ON astronomy(location, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_astronomy_jobs_enabled_run
    ON astronomy_jobs(enabled, last_run_at);
"""


def get_db():
    if "db" not in g:
        g.db = psycopg.connect(
            current_app.config["DATABASE_URL"],
            row_factory=dict_row,
        )
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.execute(SCHEMA)
        db.commit()
