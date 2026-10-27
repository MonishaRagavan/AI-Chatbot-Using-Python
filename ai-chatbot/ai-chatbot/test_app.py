"""
Automated tests. Run with:  python -m unittest -v
Uses demo mode and a temporary database, so no API key is needed
and your real chatbot.db is not touched.
"""
import os
import tempfile
import unittest

# Settings must be set BEFORE app.py is imported.
os.environ["MOCK_MODE"] = "true"
os.environ["DASHBOARD_PASSWORD"] = "test-pass"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["CHATBOT_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as chatbot  # noqa: E402

chatbot.time.sleep = lambda s: None  # skip the 1-second demo delay


class ChatbotTests(unittest.TestCase):
    def setUp(self):
        chatbot.request_log.clear()
        self.client = chatbot.app.test_client()

    def login(self):
        return self.client.post("/login", data={"password": "test-pass"})

    def test_home_page_loads(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"AI Chatbot", r.data)

    def test_chat_returns_reply(self):
        r = self.client.post("/api/chat", json={"message": "hello", "history": []})
        self.assertEqual(r.status_code, 200)
        self.assertIn("demo mode", r.get_json()["reply"])

    def test_empty_message_rejected(self):
        r = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(r.status_code, 400)

    def test_too_long_message_rejected(self):
        r = self.client.post("/api/chat", json={"message": "a" * 2001})
        self.assertEqual(r.status_code, 400)

    def test_bad_json_rejected(self):
        r = self.client.post("/api/chat", data="not json", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_rate_limit(self):
        codes = [self.client.post("/api/chat", json={"message": "hi"}).status_code for _ in range(22)]
        self.assertIn(429, codes)

    def test_dashboard_requires_login(self):
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.assertEqual(self.client.get("/api/dashboard/stats").status_code, 401)

    def test_wrong_password_rejected(self):
        r = self.client.post("/login", data={"password": "wrong"})
        self.assertIn(b"Wrong password", r.data)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_dashboard_shows_logged_chats(self):
        self.client.post("/api/chat", json={"message": "what is python"})
        self.client.post("/api/chat", json={"message": "x" * 2001})  # fails validation, not logged
        self.login()
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        data = self.client.get("/api/dashboard/stats").get_json()
        self.assertGreaterEqual(data["total"], 1)
        self.assertEqual(data["mode"], "demo")
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual(data["recent"][0]["user_message"], "what is python")

    def test_logout(self):
        self.login()
        self.client.post("/logout")
        self.assertEqual(self.client.get("/dashboard").status_code, 302)


if __name__ == "__main__":
    unittest.main()
