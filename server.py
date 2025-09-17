# server.py
from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# Config: correct credentials (for testing)
CORRECT_USER = "admin"
CORRECT_PASS = "s3cr3t"

# Simple in-memory failed-attempt tracker by IP
FAILED = {}
LOCK_THRESHOLD = 5        # fail attempts before temporary lock
LOCK_DURATION = 30       # seconds

def is_locked(ip):
    info = FAILED.get(ip)
    if not info:
        return False
    fails, locked_until = info
    if locked_until and time.time() < locked_until:
        return True
    return False

@app.route("/login", methods=["POST"])
def login():
    ip = request.remote_addr or "unknown"
    if is_locked(ip):
        return jsonify({"result": "locked", "message": "Too many attempts. Try later."}), 429

    username = request.form.get("username") or request.json.get("username")
    password = request.form.get("password") or request.json.get("password")

    # Simple check
    if username == CORRECT_USER and password == CORRECT_PASS:
        # reset fails on success
        if ip in FAILED:
            del FAILED[ip]
        return jsonify({"result": "success", "message": "Welcome!"}), 200

    # failed attempt
    fails, _ = FAILED.get(ip, (0, None))
    fails += 1
    locked_until = None
    if fails >= LOCK_THRESHOLD:
        locked_until = time.time() + LOCK_DURATION
    FAILED[ip] = (fails, locked_until)
    return jsonify({"result": "fail", "message": "Invalid credentials."}), 200

@app.route("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    # Run only on localhost
    app.run(host="127.0.0.1", port=5000)
