#!/usr/bin/env python3
"""Migrate astronomy rows from the legacy Flask SQLite database to PostgreSQL."""

import argparse
import os
import sqlite3

import psycopg


COLUMNS = [
    "id", "timestamp", "location", "country_name", "state_prov", "city", "locality",
    "latitude", "longitude", "elevation", "mid_night", "night_end",
    "morn_astronomical_twilight_begin", "morn_astronomical_twilight_end",
    "morn_nautical_twilight_begin", "morn_nautical_twilight_end",
    "morn_civil_twilight_begin", "morn_civil_twilight_end",
    "morn_blue_hour_begin", "morn_blue_hour_end", "morn_golden_hour_begin",
    "morn_golden_hour_end", "sunrise", "sunset", "eve_golden_hour_begin",
    "eve_golden_hour_end", "eve_blue_hour_begin", "eve_blue_hour_end",
    "eve_civil_twilight_begin", "eve_civil_twilight_end",
    "eve_nautical_twilight_begin", "eve_nautical_twilight_end",
    "eve_astronomical_twilight_begin", "eve_astronomical_twilight_end",
    "night_begin", "sun_status", "solar_noon", "day_length", "sun_altitude",
    "sun_distance", "sun_azimuth", "moon_phase", "moonrise", "moonset",
    "moon_status", "moon_altitude", "moon_distance", "moon_azimuth",
    "moon_parallactic_angle", "moon_illumination_percentage", "moon_angle",
]


def migrate(sqlite_path: str, database_url: str) -> int:
    sqlite = sqlite3.connect(os.path.expanduser(sqlite_path))
    sqlite.row_factory = sqlite3.Row
    rows = sqlite.execute(
        "SELECT " + ", ".join(COLUMNS) + " FROM astronomy ORDER BY id"
    ).fetchall()
    sqlite.close()

    placeholders = ", ".join(["%s"] * len(COLUMNS))
    columns = ", ".join(COLUMNS)
    sql = f"""
        INSERT INTO astronomy ({columns})
        VALUES ({placeholders})
        ON CONFLICT DO NOTHING
    """

    with psycopg.connect(database_url) as pg:
        with pg.cursor() as cur:
            cur.executemany(sql, [tuple(row[c] for c in COLUMNS) for row in rows])
            cur.execute("SELECT setval(pg_get_serial_sequence('astronomy', 'id'), COALESCE((SELECT MAX(id) FROM astronomy), 1), true)")

    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sqlite",
        default=os.path.expanduser("~/local/data/flaskr.sqlite"),
        help="Path to the legacy Flask SQLite database",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")

    count = migrate(args.sqlite, args.database_url)
    print(f"Read and migrated {count} legacy astronomy rows.")
