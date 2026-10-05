from flask import Blueprint,current_app,jsonify,render_template,request
from .db import get_db
from .tasks import fetch_apod_data,format_apod
bp=Blueprint("astronomy",__name__)

@bp.route("/")
@bp.route("/astronomy")
def astronomy_table():
    selected=request.args.get("location","").strip()
    q="SELECT * FROM astronomy"; params=()
    if selected: q+=" WHERE location=%s"; params=(selected,)
    q+=" ORDER BY timestamp DESC LIMIT 500"
    rows=get_db().execute(q,params).fetchall()
    locs=get_db().execute("SELECT DISTINCT location FROM astronomy WHERE location IS NOT NULL ORDER BY location").fetchall()
    return render_template("astronomy.html",records=rows,locations=[r["location"] for r in locs],selected=selected,current_location=current_app.config.get("CURRENT_LOCATION",""))

@bp.route("/api/apod")
def apod():
    data=fetch_apod_data()
    return (jsonify(format_apod(data)),200) if data else (jsonify({"error":"APOD unavailable"}),503)

@bp.route("/api/latest")
def latest():
    row=get_db().execute("SELECT * FROM astronomy ORDER BY id DESC LIMIT 1").fetchone()
    return (jsonify(row),200) if row else (jsonify({"error":"No astronomy data"}),404)
