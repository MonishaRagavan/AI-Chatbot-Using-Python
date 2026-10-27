# AI Chatbot with Dashboard (Flask + Gemini)

A responsive web chatbot (Python, Flask, HTML, CSS, JavaScript) with a password-protected
admin dashboard that shows usage statistics. The API key stays on the server.

## Features
- Chat page: typing indicator, loading lock, Enter to send, Clear chat, example prompts, mobile friendly
- Session memory (the browser sends recent history with each message)
- Demo mode that works with no API key
- Dashboard (`/dashboard`): total chats, chats today, success rate, average answer time,
  failed chats, 7-day chart, most common errors, latest conversations. Auto-refreshes.
- Security: key in `.env`, input validation, request size limit, per-IP rate limits,
  login rate limit, safe error messages, security headers, `textContent` rendering

## Setup (Windows)
```
cd ai-chatbot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Edit `.env`:
- `GEMINI_API_KEY`: free key from https://aistudio.google.com/ (empty = demo mode)
- `DASHBOARD_PASSWORD`: choose a password (empty = dashboard disabled)
- `SECRET_KEY`: run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the result

## Run
```
python app.py
```
- Chat: http://127.0.0.1:5000
- Dashboard: http://127.0.0.1:5000/dashboard

## Test
```
python -m unittest -v
```

## Files
| File | Purpose |
|---|---|
| `app.py` | Routes, validation, Gemini call, login |
| `db.py` | SQLite logging and statistics queries |
| `templates/` | `index.html` (chat), `login.html`, `dashboard.html` |
| `static/` | `style.css`, `script.js` (chat); `dashboard.css`, `dashboard.js` |
| `test_app.py` | Automated tests |

## Privacy
The dashboard stores the first 500 characters of each message and reply in `chatbot.db`.
Tell users this if others will use your chatbot. Delete `chatbot.db` to erase all logs.

## Troubleshooting
| Problem | Fix |
|---|---|
| `python` not recognised | Reinstall Python and tick "Add python.exe to PATH" |
| `No module named flask` | Activate the venv, then `pip install -r requirements.txt` |
| "Demo mode" badge | `.env` missing or `GEMINI_API_KEY` empty |
| Dashboard says it is turned off | Set `DASHBOARD_PASSWORD` in `.env`, restart |
| Logged out after restart | Set a fixed `SECRET_KEY` in `.env` |
| "Model not found" | Update `GEMINI_MODEL` in `.env` |
| `.env` ignored | Check it is not saved as `.env.txt` |
| Port 5000 busy | Change the last line of `app.py` to `app.run(port=5001, ...)` |

## Deployment
Use gunicorn (Linux hosts such as Render/Railway) or waitress (Windows), never `app.run()`.
Set `FLASK_DEBUG=false`, a strong `DASHBOARD_PASSWORD` and `SECRET_KEY` in the host's
environment settings, and serve over HTTPS. SQLite files can be erased on some hosts when they
redeploy; use a persistent disk or a hosted database for long-term stats.
