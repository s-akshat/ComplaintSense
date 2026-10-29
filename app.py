"""
app.py - the Flask web server. It connects the browser (HTML/CSS/JS) to the Python logic.

  Browser page  --fetch()-->  /api/... route in this file  -->  complaints.py / auth.py / analytics.py  -->  SQLite

Run it with:   python app.py      then open  http://127.0.0.1:5000
"""

import os
import secrets
import time
from functools import wraps

from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.exceptions import HTTPException

import analytics
import auth
import complaints
import database
import priority

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 60

RATING_LABELS = {1: "Very Low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very High"}


def get_secret_key():
    """The secret key signs the login cookie. Use SECRET_KEY if set, else make one and keep it
    in a local file (.secret_key) that is ignored by Git."""
    from_env = os.environ.get("SECRET_KEY")
    if from_env:
        return from_env
    path = os.path.join(BASE_DIR, ".secret_key")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return file.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as file:
        file.write(key)
    return key


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = get_secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"   # blocks most cross-site request attacks
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024     # reject huge requests

    database.init_db()
    failed_logins = {}  # (ip, username) -> {"count": n, "first": time}

    # ---------- helpers ----------

    def json_body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def admin_api(view):
        """Decorator: the API route only works for a logged-in administrator."""
        @wraps(view)
        def wrapper(*args, **kwargs):
            if session.get("role") != "admin":
                return jsonify(error="Admin login required."), 401
            return view(*args, **kwargs)
        return wrapper

    def admin_page(view):
        """Decorator: the page redirects to the login page if not logged in as admin."""
        @wraps(view)
        def wrapper(*args, **kwargs):
            if session.get("role") != "admin":
                return redirect(url_for("login_page"))
            return view(*args, **kwargs)
        return wrapper

    @app.context_processor
    def inject_user():
        return {"admin_name": session.get("name") if session.get("role") == "admin" else None}

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    # ---------- error handling ----------

    @app.errorhandler(complaints.ValidationError)
    def handle_validation(err):
        return jsonify(error="Please correct the highlighted problems.", fields=err.errors), 400

    @app.errorhandler(complaints.NotFoundError)
    def handle_not_found(err):
        return jsonify(error=str(err)), 404

    @app.errorhandler(HTTPException)
    def handle_http(err):
        if request.path.startswith("/api/"):
            return jsonify(error=err.description), err.code
        if err.code == 404:
            return render_template("404.html"), 404
        return err

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unexpected error")
        if request.path.startswith("/api/"):
            return jsonify(error="Something went wrong on the server."), 500
        return "Something went wrong.", 500

    # ---------- pages ----------

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/submit")
    def submit_page():
        return render_template("submit.html")

    @app.route("/track")
    def track_page():
        return render_template("track.html")

    @app.route("/admin/login")
    def login_page():
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return render_template("login.html")

    @app.route("/admin")
    @admin_page
    def admin_dashboard():
        return render_template("admin.html")

    @app.route("/analytics")
    @admin_page
    def analytics_page():
        return render_template("analytics.html")

    # ---------- public API ----------

    @app.route("/api/meta")
    def meta():
        return jsonify(
            categories=complaints.CATEGORIES,
            statuses=complaints.STATUSES,
            levels=analytics.LEVELS,
            emergency_categories=sorted(priority.EMERGENCY_CATEGORIES),
            rating_labels=RATING_LABELS,
        )

    @app.route("/api/complaints", methods=["POST"])
    def submit_complaint():
        result = complaints.create_complaint(json_body())
        return jsonify(result), 201

    @app.route("/api/complaints/<complaint_id>")
    def track_complaint(complaint_id):
        return jsonify(complaints.get_public_status(complaint_id))

    # ---------- login / logout ----------

    @app.route("/api/login", methods=["POST"])
    def login():
        data = json_body()
        username, password = data.get("username"), data.get("password")
        if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
            return jsonify(error="Enter both username and password."), 400

        key = (request.remote_addr, username.strip().lower())
        entry = failed_logins.get(key)
        if entry and time.time() - entry["first"] > LOCKOUT_SECONDS:
            failed_logins.pop(key, None)
            entry = None
        if entry and entry["count"] >= MAX_FAILED_LOGINS:
            return jsonify(error="Too many failed attempts. Please wait a minute and try again."), 429

        user = auth.authenticate(username, password)
        if user is None:
            entry = failed_logins.setdefault(key, {"count": 0, "first": time.time()})
            entry["count"] += 1
            return jsonify(error="Invalid username or password."), 401
        if not auth.is_admin(user):
            return jsonify(error="This account is not allowed to use the admin panel."), 403

        failed_logins.pop(key, None)
        session.clear()  # start a fresh session after login
        session["user_id"] = user["user_id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        return jsonify(name=user["name"])

    @app.route("/api/logout", methods=["POST"])
    def logout():
        session.clear()
        return jsonify(ok=True)

    # ---------- admin API ----------

    @app.route("/api/admin/complaints")
    @admin_api
    def admin_list():
        args = request.args
        items = complaints.list_complaints(
            status=args.get("status") or None,
            category=args.get("category") or None,
            level=args.get("level") or None,
            search=args.get("search") or None,
            sort=args.get("sort") or "priority",
        )
        return jsonify(items)

    @app.route("/api/admin/complaints/<complaint_id>")
    @admin_api
    def admin_get(complaint_id):
        return jsonify(complaints.get_complaint_admin(complaint_id))

    @app.route("/api/admin/complaints/<complaint_id>", methods=["PATCH"])
    @admin_api
    def admin_update(complaint_id):
        data = json_body()
        kwargs = {"new_status": data.get("status"), "remarks": data.get("remarks")}
        if "assigned_to" in data:
            kwargs["assigned_to"] = data["assigned_to"]
        updated = complaints.update_complaint(complaint_id, session["user_id"], **kwargs)
        return jsonify(updated)

    @app.route("/api/admin/complaints/<complaint_id>", methods=["DELETE"])
    @admin_api
    def admin_delete(complaint_id):
        complaints.delete_complaint(complaint_id)
        return jsonify(ok=True)

    @app.route("/api/admin/staff")
    @admin_api
    def admin_staff():
        return jsonify(auth.list_admins())

    @app.route("/api/admin/stats")
    @admin_api
    def admin_stats():
        return jsonify(analytics.get_stats())

    @app.route("/api/admin/charts/<kind>.png")
    @admin_api
    def admin_chart(kind):
        if kind not in analytics.CHARTS:
            return jsonify(error="Unknown chart."), 404
        response = Response(analytics.make_chart(kind), mimetype="image/png")
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
