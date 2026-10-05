import os
import json

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from .db import get_db
from .tasks import fetch_apod_data, format_apod, run_astronomy_job

bp = Blueprint("astronomy", __name__)


def location_options():
    try:
        with open(current_app.config["LOCATIONS_FILE"], encoding="utf-8") as f:
            data = json.load(f)
        return [
            {"name": name, "latitude": coords[0], "longitude": coords[1]}
            for name, coords in data.items()
        ]
    except (FileNotFoundError, json.JSONDecodeError, TypeError, IndexError):
        return []


@bp.route("/")
@bp.route("/astronomy")
def astronomy_current():
    current_location = current_app.config.get("CURRENT_LOCATION", "").strip()
    row = get_db().execute(
        """SELECT * FROM astronomy
           WHERE location = %s
           ORDER BY timestamp DESC
           LIMIT 1""",
        (current_location,),
    ).fetchone()
    return render_template(
        "astronomy.html",
        record=row,
        current_location=current_location,
    )


@bp.route("/historical")
def astronomy_historical():
    selected = request.args.get("location", "").strip()
    query = "SELECT * FROM astronomy"
    params = ()
    if selected:
        query += " WHERE location = %s"
        params = (selected,)
    query += " ORDER BY timestamp DESC LIMIT 500"
    rows = get_db().execute(query, params).fetchall()
    locs = get_db().execute(
        "SELECT DISTINCT location FROM astronomy WHERE location IS NOT NULL ORDER BY location"
    ).fetchall()
    return render_template(
        "historical.html",
        records=rows,
        locations=[row["location"] for row in locs],
        selected=selected,
        current_location=current_app.config.get("CURRENT_LOCATION", ""),
    )


@bp.route("/control", methods=("GET", "POST"))
def control():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "delete":
            db.execute("DELETE FROM astronomy_jobs WHERE id = %s", (request.form["job_id"],))
            db.commit()
            flash("Astronomy job removed.", "success")
            return redirect(url_for("astronomy.control"))

        if action == "toggle":
            db.execute(
                "UPDATE astronomy_jobs SET enabled = NOT enabled, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (request.form["job_id"],),
            )
            db.commit()
            return redirect(url_for("astronomy.control"))

        if action == "run":
            job_id = int(request.form["job_id"])
            success = run_astronomy_job(job_id)
            flash(
                "Astronomy job completed." if success else "Astronomy job failed. Check the job status.",
                "success" if success else "error",
            )
            return redirect(url_for("astronomy.control"))

        try:
            name = request.form["name"].strip()
            location = request.form["location"].strip()
            latitude = float(request.form["latitude"])
            longitude = float(request.form["longitude"])
            interval_minutes = int(request.form["interval_minutes"])
            if not name or not location:
                raise ValueError("Name and location are required.")
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("Latitude/longitude are out of range.")
            if interval_minutes not in {15, 60, 240, 1440}:
                raise ValueError("Invalid collection interval.")

            job_id = request.form.get("job_id")
            enabled = bool(request.form.get("enabled"))
            if job_id:
                db.execute(
                    """UPDATE astronomy_jobs
                       SET name=%s, location=%s, latitude=%s, longitude=%s,
                           interval_minutes=%s, enabled=%s, updated_at=CURRENT_TIMESTAMP
                       WHERE id=%s""",
                    (name, location, latitude, longitude, interval_minutes, enabled, job_id),
                )
            else:
                db.execute(
                    """INSERT INTO astronomy_jobs
                       (name, location, latitude, longitude, interval_minutes, enabled)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (name, location, latitude, longitude, interval_minutes, enabled),
                )
            db.commit()
            flash("Astronomy job saved.", "success")
        except (KeyError, ValueError) as exc:
            flash(str(exc) or "Invalid astronomy job settings.", "error")
        return redirect(url_for("astronomy.control"))

    jobs = db.execute(
        "SELECT * FROM astronomy_jobs ORDER BY enabled DESC, name"
    ).fetchall()
    return render_template(
        "control.html",
        jobs=jobs,
        locations=location_options(),
        current_location=current_app.config.get("CURRENT_LOCATION", ""),
    )


@bp.route("/api/location-search")
def location_search():
    query = request.args.get("q", "").strip().lower()
    if len(query) < 2:
        return jsonify({"locations": []})

    matches = []
    for item in location_options():
        name = item["name"].lower()
        if query in name:
            score = 0 if name.startswith(query) else (1 if f", {query}" in name else 2)
            matches.append((score, len(name), item))

    matches.sort(key=lambda item: (item[0], item[1], item[2]["name"].lower()))
    return jsonify({"locations": [item for _, _, item in matches[:12]]})


@bp.route("/apod")
def apod_page():
    data = fetch_apod_data()
    return render_template("apod.html", apod=format_apod(data) if data else None)


@bp.route("/api/apod")
def apod():
    data = fetch_apod_data()
    return (jsonify(format_apod(data)), 200) if data else (jsonify({"error": "APOD unavailable"}), 503)


@bp.route("/api/latest")
def latest():
    row = get_db().execute(
        "SELECT * FROM astronomy ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return (jsonify(row), 200) if row else (jsonify({"error": "No astronomy data"}), 404)


@bp.context_processor
def navigation_context():
    return {"hostname": os.uname().nodename}
