import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import requests
from flask import current_app

from .db import get_db

VALID_COLUMNS = [
    "location", "country_name", "state_prov", "city", "locality",
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


def load_locations():
    try:
        with open(current_app.config["LOCATIONS_FILE"], encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_location_coordinates(query):
    query = (query or "").lower()
    for name, coords in load_locations().items():
        if query in name.lower():
            return float(coords[0]), float(coords[1])
    return None, None


def fetch_astronomy_at_coordinates(latitude, longitude, display_name=None):
    key = current_app.config.get("IPGEOLOCATION_API_KEY") or os.environ.get(
        "IPGEOLOCATION_API_KEY"
    )
    if not key:
        print("Astronomy API key is not configured.")
        return {}
    try:
        response = requests.get(
            "https://api.ipgeolocation.io/astronomy",
            params={"apiKey": key, "lat": latitude, "long": longitude},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if display_name:
            location = data.get("location")
            if not isinstance(location, dict):
                location = {}
            location["city"] = display_name
            data["location"] = location
        return data
    except requests.RequestException as exc:
        print(f"Astronomy API error: {exc}")
        return {}


def fetch_astronomy_data(location_query):
    lat, lon = get_location_coordinates(location_query)
    if lat is None:
        return {}
    return fetch_astronomy_at_coordinates(lat, lon, location_query)

def celestial_status(altitude):
    """Return whether a celestial body is above or below the horizon."""
    try:
        return "Above horizon" if float(altitude) >= 0 else "Below horizon"
    except (TypeError, ValueError):
        return "-"

def process_and_insert_astronomy_data(api_data=None):
    if api_data is None:
        location = current_app.config.get("CURRENT_LOCATION")
        if not location:
            return False
        api_data = fetch_astronomy_data(location)
    if not api_data:
        return False

    info = api_data.get("location", {})
    if not isinstance(info, dict):
        info = {}

    payload = {
        "location": info.get("city") or api_data.get("city"),
        "country_name": info.get("country_name"),
        "state_prov": info.get("state_prov"),
        "city": info.get("city") or api_data.get("city"),
        "locality": info.get("locality"),
        "latitude": info.get("latitude") or api_data.get("latitude"),
        "longitude": info.get("longitude") or api_data.get("longitude"),
        "elevation": info.get("elevation") or api_data.get("elevation"),
    }
    for key in VALID_COLUMNS:
        if key not in payload:
            value = api_data.get(key)
            payload[key] = None if isinstance(value, (dict, list)) else value

    payload["sun_status"] = celestial_status(payload.get("sun_altitude"))
    payload["moon_status"] = celestial_status(payload.get("moon_altitude"))
    columns = ", ".join(payload)
    values = ", ".join(f"%({key})s" for key in payload)
    db = get_db()
    db.execute(
        f"INSERT INTO astronomy ({columns}) VALUES ({values})",
        payload,
    )
    db.commit()
    return True


def fetch_and_store_astronomy(location_query=None):
    if location_query:
        return process_and_insert_astronomy_data(fetch_astronomy_data(location_query))
    return process_and_insert_astronomy_data()


def run_astronomy_job(job_id):
    db = get_db()
    job = db.execute(
        "SELECT * FROM astronomy_jobs WHERE id = %s AND enabled = TRUE",
        (job_id,),
    ).fetchone()
    if not job:
        return False

    try:
        api_data = fetch_astronomy_at_coordinates(
            job["latitude"], job["longitude"], job["location"]
        )
        success = process_and_insert_astronomy_data(api_data)
        db.execute(
            """UPDATE astronomy_jobs
               SET last_run_at = CURRENT_TIMESTAMP,
                   last_status = %s,
                   last_error = NULL,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            ("completed" if success else "failed", job_id),
        )
        db.commit()
        return success
    except Exception as exc:
        db.rollback()
        db.execute(
            """UPDATE astronomy_jobs
               SET last_run_at = CURRENT_TIMESTAMP,
                   last_status = 'failed',
                   last_error = %s,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (str(exc), job_id),
        )
        db.commit()
        print(f"Astronomy job {job_id} failed: {exc}")
        return False


def due_astronomy_jobs():
    return get_db().execute(
        """SELECT * FROM astronomy_jobs
           WHERE enabled = TRUE
             AND (last_run_at IS NULL
                  OR last_run_at <= CURRENT_TIMESTAMP
                     - (interval_minutes * INTERVAL '1 minute'))
           ORDER BY id"""
    ).fetchall()


def run_due_astronomy_jobs():
    results = []
    for job in due_astronomy_jobs():
        results.append((job["id"], run_astronomy_job(job["id"])))
    return results


APOD_URL = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"


def fetch_apod_data():
    try:
        response = requests.get(APOD_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    except requests.RequestException:
        return None


def format_apod(apod):
    title = apod.get("title", {})
    title = title.get("rendered", "Astronomy Picture of the Day") if isinstance(title, dict) else str(title)
    description = apod.get("explanation") or apod.get("description", "")
    description = description.get("rendered", "") if isinstance(description, dict) else str(description)
    return {
        "title": title,
        "description": description,
        "media_type": apod.get("media_type", "image"),
        "url": apod.get("hdurl") or apod.get("url") or "",
        "credit": (apod.get("credit") or apod.get("copyright") or "").strip(),
    }


def fetch_latest_astronomy_data():
    row = get_db().execute(
        """SELECT sunrise,sunset,solar_noon,day_length,sun_altitude,sun_azimuth,
                  sun_distance,moon_phase,moonrise,moonset,moon_altitude,
                  moon_illumination_percentage,timestamp
           FROM astronomy ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    if not row:
        raise ValueError("No records found in astronomy table.")
    return row


def time_to_rad(value):
    if not value or str(value).strip() in {"-", "", "N/A"}:
        return 0.0
    try:
        h, m = str(value).split(":")[:2]
        return ((int(h) + int(m) / 60) / 24) * 2 * np.pi
    except (ValueError, IndexError):
        return 0.0


def generate_celestial_dial(output_dir=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = fetch_latest_astronomy_data()
    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ri, ro = .72, 1
    sunrise, sunset, solar, moonrise, moonset = [
        time_to_rad(data[key]) for key in ("sunrise", "sunset", "solar_noon", "moonrise", "moonset")
    ]
    ax.fill_between(np.linspace(sunrise, sunset, 200), ri, ro, alpha=.9, label=f"Daylight ({data['day_length']})")
    ax.fill_between(np.linspace(sunset, sunrise + 2 * np.pi, 200), ri, ro, alpha=.9, label="Night")
    ax.plot([solar, solar], [ri - .05, ro + .05], lw=2.5, linestyle="--")
    for x, radius, marker in [(sunrise, .86, "o"), (sunset, .86, "o"), (moonrise, .58, "^"), (moonset, .58, "v")]:
        ax.plot(x, radius, marker, markersize=10)
    ax.plot(np.radians(data["sun_azimuth"] or 0), 1.1, "*", markersize=15)
    hours = np.arange(0, 24, 3)
    ax.set_xticks(hours / 24 * 2 * np.pi)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], fontweight="bold")
    ax.set_yticks([])
    ax.set_ylim(0, 1.25)
    illum = float(data["moon_illumination_percentage"] or 0)
    ax.text(0, 0, f"CELESTIAL DATA\n──────────────\nDay Length: {data['day_length']}\nMoon Phase: {data['moon_phase']}\nIllumination: {illum:.2f}%\nSun Altitude: {float(data['sun_altitude'] or 0):.2f}°\nSun Distance: {float(data['sun_distance'] or 0)/1e6:.2f} M km\nMoon Altitude: {float(data['moon_altitude'] or 0):.2f}°", ha="center", va="center", fontsize=9.5, bbox=dict(boxstyle="round,pad=.7", facecolor="white", edgecolor="gray", alpha=.95))
    ax.set_title("24-Hour Solar & Lunar Cycle Dial", fontweight="bold", pad=25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.38, 1.08))
    plt.tight_layout()
    directory = Path(output_dir or current_app.config["ASTRONOMY_MEDIA_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"celestial_dial_{datetime.now():%Y%m%d_%H%M%S}.png"
    plt.savefig(directory / filename, dpi=75, bbox_inches="tight")
    plt.close(fig)
    return filename


def moon_phase_polygon(illumination, phase_name):
    waxing = any(p in (phase_name or "").upper() for p in ("WAXING", "FIRST", "NEW"))
    y = np.linspace(1, -1, 100)
    k = illumination / 50 - 1
    outer = np.sqrt(np.maximum(0, 1 - y * y))
    term = k * outer
    x = np.concatenate([outer, term[::-1]]) if waxing else np.concatenate([-outer, (-term)[::-1]])
    return np.column_stack([x, np.concatenate([y, y[::-1]])])


def generate_current_moon_phase(output_file=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    row = get_db().execute(
        "SELECT timestamp,moon_illumination_percentage,moon_phase FROM astronomy ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise ValueError("No records found in astronomy table.")
    from matplotlib.patches import Circle, Polygon
    illum = float(row["moon_illumination_percentage"] or 0)
    phase = row["moon_phase"] or "UNKNOWN"
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.add_patch(Circle((0, 0), 1, color="#2b2d38"))
    if illum >= 99.5:
        ax.add_patch(Circle((0, 0), 1, color="#fefcd7"))
    elif illum > .5:
        ax.add_patch(Polygon(moon_phase_polygon(illum, phase), color="#fefcd7"))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Current Moon Phase\n{row['timestamp']}", fontsize=14)
    ax.text(0, -1.3, f"Phase: {phase} ({illum:.1f}%)", ha="center")
    path = Path(output_file or current_app.config["ASTRONOMY_MEDIA_DIR"]) / "current_moon_phase.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return str(path)
