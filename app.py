from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from io import StringIO
import pandas as pd
import random
import time
import logging

app = Flask(__name__)
app.secret_key = "secret_key_for_demo"

# ----------------------------
# Logging Setup
# ----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Silence Azure SDK noisy logs
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

# ----------------------------
# Azure Blob Storage Config
# ----------------------------
import os
from dotenv import load_dotenv

load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
BLOB_NAME = "dashboard/latest_anomaly_results.csv"

# ----------------------------
# Dummy User Credentials
# ----------------------------
USERS = {
    "admin": {"password": "password123", "email": "admin@example.com", "name": "Admin User"},
    "user1": {"password": "user1234", "email": "user1@example.com", "name": "John Doe"}
}

# ----------------------------
# Security State
# ----------------------------
FAILED_LOGIN_ATTEMPTS = {}
BLOCKED_IPS = {}

MAX_FAILED_ATTEMPTS = 5
BLOCK_DURATION_MINUTES = 5

# ----------------------------
# Utility Functions
# ----------------------------
def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"

def is_ip_blocked(ip):
    if ip in BLOCKED_IPS:
        if datetime.now() < BLOCKED_IPS[ip]:
            return True
        else:
            del BLOCKED_IPS[ip]
    return False

def register_failed_login(ip):
    now = datetime.now()
    if ip not in FAILED_LOGIN_ATTEMPTS:
        FAILED_LOGIN_ATTEMPTS[ip] = []

    FAILED_LOGIN_ATTEMPTS[ip] = [
        t for t in FAILED_LOGIN_ATTEMPTS[ip]
        if now - t < timedelta(minutes=10)
    ]

    FAILED_LOGIN_ATTEMPTS[ip].append(now)

    if len(FAILED_LOGIN_ATTEMPTS[ip]) >= MAX_FAILED_ATTEMPTS:
        BLOCKED_IPS[ip] = now + timedelta(minutes=BLOCK_DURATION_MINUTES)
        logging.warning(f"IP BLOCKED due to brute-force: {ip}")

def simulate_latency(min_ms=100, max_ms=800):
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    time.sleep(delay)

# ----------------------------
# Request Logging Middleware
# ----------------------------
@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    latency = round((time.time() - request.start_time) * 1000, 2)
    ip = get_client_ip()

    logging.info(
        f"IP={ip} | METHOD={request.method} | PATH={request.path} | "
        f"STATUS={response.status_code} | LATENCY_MS={latency}"
    )

    response.headers["X-Response-Time-ms"] = str(latency)
    return response

# ----------------------------
# Load Azure ML Anomaly CSV from Blob
# ----------------------------
def load_anomaly_data():
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)

        blob_data = blob_client.download_blob().readall().decode("utf-8")
        df = pd.read_csv(StringIO(blob_data))

        # Normalize columns
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Ensure required columns
        required_cols = ["source_ip", "requests", "request_rate", "login_attempts", "prediction", "reason"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        # Add time column
        df["time"] = [f"Window {i+1}" for i in range(len(df))]

        # Convert numeric fields
        df["source_ip"] = df["source_ip"].fillna("N/A")
        df["requests"] = pd.to_numeric(df["requests"], errors="coerce").fillna(0).astype(int)
        df["request_rate"] = pd.to_numeric(df["request_rate"], errors="coerce").fillna(0).astype(int)
        df["login_attempts"] = pd.to_numeric(df["login_attempts"], errors="coerce").fillna(0).astype(int)
        df["prediction"] = df["prediction"].fillna("Normal")
        df["reason"] = df["reason"].fillna("Normal Activity")

        return df

    except Exception as e:
        logging.error(f"Error loading Azure anomaly data: {e}")
        return pd.DataFrame(columns=[
            "time", "source_ip", "requests", "request_rate",
            "login_attempts", "prediction", "reason"
        ])

# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def home():
    simulate_latency(50, 250)
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    ip = get_client_ip()
    simulate_latency(100, 600)

    if is_ip_blocked(ip):
        logging.warning(f"Blocked IP attempted login: {ip}")
        return render_template("login.html", blocked=True), 403

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username in USERS and USERS[username]["password"] == password:
            session["user"] = username
            session["user_name"] = USERS[username]["name"]
            FAILED_LOGIN_ATTEMPTS.pop(ip, None)
            flash(f"Welcome back, {USERS[username]['name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            register_failed_login(ip)
            flash("Invalid username or password", "danger")
            logging.warning(f"Failed login attempt | IP={ip} | USERNAME={username}")
            return render_template("login.html"), 401

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    simulate_latency(100, 500)

    if "user" not in session:
        return redirect(url_for("login"))

    df = load_anomaly_data()

    total_windows = len(df)
    anomaly_count = len(df[df["prediction"].str.lower() == "anomaly"])
    normal_count = len(df[df["prediction"].str.lower() == "normal"])

    top_suspicious_ip = "N/A"
    anomaly_df = df[df["prediction"].str.lower() == "anomaly"]
    if not anomaly_df.empty:
        top_suspicious_ip = anomaly_df["source_ip"].mode().iloc[0]

    peak_requests = int(df["request_rate"].max()) if not df.empty else 0
    peak_login_attempts = int(df["login_attempts"].max()) if not df.empty else 0

    return render_template(
        "dashboard.html",
        user=session["user"],
        user_name=session.get("user_name", session["user"]),
        total_windows=total_windows,
        anomaly_count=anomaly_count,
        normal_count=normal_count,
        top_suspicious_ip=top_suspicious_ip,
        peak_requests=peak_requests,
        peak_login_attempts=peak_login_attempts
    )

@app.route("/activity")
def activity():
    simulate_latency(100, 700)

    if "user" not in session:
        return redirect(url_for("login"))

    df = load_anomaly_data()
    activities = df.to_dict(orient="records")

    return render_template(
        "activity.html",
        user=session["user"],
        user_name=session.get("user_name"),
        activities=activities
    )

@app.route("/settings", methods=["GET", "POST"])
def settings():
    simulate_latency(120, 800)

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        new_email = request.form.get("email")
        USERS[session["user"]]["email"] = new_email
        flash("Settings updated successfully!", "success")
        return redirect(url_for("settings"))

    user_data = USERS.get(session["user"], {})
    return render_template(
        "settings.html",
        user=session["user"],
        user_name=session.get("user_name"),
        email=user_data.get("email")
    )

@app.route("/logout")
def logout():
    simulate_latency(50, 200)
    session.pop("user", None)
    session.pop("user_name", None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("home"))

# ----------------------------
# Extra Fake Security Endpoints
# ----------------------------
@app.route("/admin")
def admin():
    simulate_latency(200, 1200)
    return "Forbidden", 403

@app.route("/secret")
def secret():
    simulate_latency(300, 1500)
    return "Unauthorized Access", 401

@app.route("/api/data")
def api_data():
    simulate_latency(150, 900)
    return jsonify({"status": "ok", "records": random.randint(50, 200)}), 200

@app.route("/health")
def health():
    simulate_latency(50, 150)
    return jsonify({"status": "healthy"}), 200

@app.route("/report")
def report():
    simulate_latency(400, 2000)
    if random.random() < 0.2:
        raise Exception("Simulated internal server error")
    return jsonify({"report": "generated"}), 200

# ----------------------------
# Error Handlers
# ----------------------------
@app.errorhandler(404)
def page_not_found(e):
    simulate_latency(50, 300)
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f"Internal server error: {str(e)}")
    return "Internal Server Error", 500

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)