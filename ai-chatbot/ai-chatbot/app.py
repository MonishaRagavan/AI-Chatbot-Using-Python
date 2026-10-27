"""
AI Chatbot - Flask backend with an admin dashboard.
  /              the chat page
  /api/chat      chat endpoint (browser -> this file -> Gemini)
  /login         dashboard login
  /dashboard     usage statistics (password protected)
The API key stays on the server and is never sent to the browser.
"""

import hmac
import os
import re
import secrets
import time
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import (Flask, jsonify, redirect, render_template, request,
                   session, url_for)

import db

load_dotenv()  # read the .env file into environment variables

app = Flask(__name__)

# ---------- Settings ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true" or not GEMINI_API_KEY
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_ITEMS = 20
RATE_LIMIT_PER_MINUTE = 20
LOGIN_ATTEMPTS_PER_MINUTE = 5

app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # reject requests bigger than 64 KB
# If SECRET_KEY is missing we make a random one (you will just be logged out on restart).
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True   # JavaScript cannot read the cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # blocks most cross-site request tricks

SYSTEM_PROMPT = (
    "You are a friendly, helpful AI assistant. "
    "Give clear, accurate, concise answers. "
    "Use simple language and short examples when explaining things."
)

request_log = {}  # remembers recent request times per key (resets on restart)
db.init_db()


class ChatError(Exception):
    """An error with a safe message that can be shown to the user."""

    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------- Helpers ----------
def is_rate_limited(key, limit):
    """True if `key` made `limit` or more requests in the last 60 seconds."""
    now = time.time()
    recent = [t for t in request_log.get(key, []) if now - t < 60]
    if len(recent) >= limit:
        request_log[key] = recent
        return True
    recent.append(now)
    request_log[key] = recent
    return False


def validate_request(data):
    """Check the data sent by the browser. Returns (message, clean_history)."""
    if not isinstance(data, dict):
        raise ChatError("Invalid request. Please send JSON data.", 400)

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ChatError("Please type a message first.", 400)
    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ChatError(
            f"Your message is too long. Please keep it under {MAX_MESSAGE_LENGTH} characters.", 400)

    raw_history = data.get("history", [])
    if not isinstance(raw_history, list):
        raise ChatError("Invalid conversation history.", 400)

    clean_history = []
    for item in raw_history[-MAX_HISTORY_ITEMS:]:
        if (isinstance(item, dict)
                and item.get("role") in ("user", "assistant")
                and isinstance(item.get("content"), str)
                and item["content"].strip()):
            clean_history.append(
                {"role": item["role"], "content": item["content"][:MAX_MESSAGE_LENGTH]})

    while clean_history and clean_history[0]["role"] != "user":
        clean_history.pop(0)  # Gemini wants the conversation to start with the user
    return message, clean_history


def mock_reply(message):
    """Fake AI for demo mode (no API key needed)."""
    text = message.lower()
    if any(w in re.findall(r"[a-z]+", text) for w in ("hello", "hi", "hey")):
        reply = "Hello! I'm running in demo mode, so my answers are pre-written."
    elif "python" in text:
        reply = ("Python is a beginner-friendly programming language. "
                 "Example: print('Hello') shows the word Hello on screen.")
    elif "flask" in text:
        reply = "Flask is a small Python framework for building websites and web APIs."
    else:
        reply = ("This is a demo reply. Add your Gemini API key to the .env file "
                 "to get real AI answers. You asked: " + message[:100])
    time.sleep(1)  # pretend to think so you can see the typing indicator
    return reply


def ask_gemini(history, message):
    """Send the conversation to Gemini and return the answer text."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

    contents = []
    for item in history:
        role = "model" if item["role"] == "assistant" else "user"  # Gemini says "model"
        contents.append({"role": role, "parts": [{"text": item["content"]}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": contents}
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.exceptions.Timeout:
        raise ChatError("The AI took too long to respond. Please try again.", 504)
    except requests.exceptions.RequestException:
        raise ChatError("Could not connect to the AI service. Check the internet connection.", 502)

    if response.status_code != 200:
        print(f"[Gemini error] status={response.status_code} body={response.text[:300]}")
        if response.status_code in (401, 403):
            raise ChatError("The server's API key is invalid or not allowed.", 502)
        if response.status_code == 404:
            raise ChatError("The AI model was not found. Check GEMINI_MODEL in .env.", 502)
        if response.status_code == 429:
            raise ChatError("Too many requests to the AI right now. Please wait and retry.", 429)
        if response.status_code == 400:
            raise ChatError("The AI could not accept this request. Try rephrasing.", 400)
        raise ChatError("The AI service had a problem. Please try again later.", 502)

    try:
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ChatError("The AI could not answer that. Try rephrasing your question.", 422)
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
    except ValueError:
        raise ChatError("Received an unreadable response from the AI.", 502)

    if not text:
        raise ChatError("The AI returned an empty answer. Try rephrasing.", 422)
    return text


def safe_log(message, reply, status, error_text, started):
    """Save the chat for the dashboard. A logging problem must never break the chat."""
    try:
        db.log_chat(message, reply, status, error_text,
                    int((time.time() - started) * 1000), "demo" if MOCK_MODE else "live")
    except Exception as err:
        print(f"[Log error] {err}")


def login_required(view):
    """Only let logged-in admins open a page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


# ---------- Chat routes ----------
@app.route("/")
def index():
    return render_template("index.html", mock_mode=MOCK_MODE,
                           dashboard_enabled=bool(DASHBOARD_PASSWORD))


@app.route("/api/chat", methods=["POST"])
def chat():
    started = time.time()
    message = None  # stays None if the request fails before validation
    try:
        if is_rate_limited("chat:" + (request.remote_addr or "unknown"), RATE_LIMIT_PER_MINUTE):
            raise ChatError("You are sending messages too quickly. Please wait a moment.", 429)

        message, history = validate_request(request.get_json(silent=True))
        reply = mock_reply(message) if MOCK_MODE else ask_gemini(history, message)
        safe_log(message, reply, "ok", None, started)
        return jsonify({"reply": reply})

    except ChatError as err:
        if message is not None:
            safe_log(message, None, "error", err.message, started)
        return jsonify({"error": err.message}), err.status_code
    except Exception as err:  # last safety net
        print(f"[Unexpected error] {err}")
        if message is not None:
            safe_log(message, None, "error", "Something went wrong on the server.", started)
        return jsonify({"error": "Something went wrong on the server."}), 500


# ---------- Dashboard routes ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if not DASHBOARD_PASSWORD:
        return render_template("login.html", disabled=True, error=None), 503
    error = None
    if request.method == "POST":
        if is_rate_limited("login:" + (request.remote_addr or "unknown"), LOGIN_ATTEMPTS_PER_MINUTE):
            error = "Too many attempts. Wait a minute and try again."
        else:
            given = request.form.get("password", "")
            # compare_digest compares in constant time (safer than ==)
            if hmac.compare_digest(given.encode(), DASHBOARD_PASSWORD.encode()):
                session.clear()
                session["admin"] = True
                return redirect(url_for("dashboard"))
            error = "Wrong password."
    return render_template("login.html", disabled=False, error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/dashboard/stats")
@login_required
def dashboard_stats():
    data = db.get_stats()
    data.update({
        "mode": "demo" if MOCK_MODE else "live",
        "model": None if MOCK_MODE else GEMINI_MODEL,
        "daily": db.get_daily(7),
        "recent": db.get_recent(15),
        "top_errors": db.get_top_errors(5),
    })
    return jsonify(data)


# ---------- Global handlers ----------
@app.errorhandler(413)
def too_large(_err):
    return jsonify({"error": "Your request is too large."}), 413


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith(("/dashboard", "/api/dashboard", "/login")):
        response.headers["Cache-Control"] = "no-store"  # don't keep admin pages in cache
    return response


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
