"""Tests for the Kudos demo app."""

import tempfile
import unittest
from pathlib import Path

from app import create_app, get_db


class KudosAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        database = str(Path(self.temp_dir.name) / "test.sqlite")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": database,
                "DEMO_MODE": True,
                "APP_ENV": "testing",
            }
        )
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["csrf_token"] = "test-csrf"

    def csrf_headers(self):
        return {"X-CSRF-Token": "test-csrf"}

    def send_kudos(self, recipient_id=2, message="Thanks for helping me!"):
        return self.client.post(
            "/api/kudos",
            json={
                "recipient_id": recipient_id,
                "message": message,
                "idempotency_key": "test-request-1",
            },
            headers=self.csrf_headers(),
        )

    def test_employee_can_send_kudos_and_see_it_in_feed(self):
        response = self.send_kudos()
        self.assertEqual(response.status_code, 201)

        feed = self.client.get("/api/kudos")
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.json["items"][0]["sender_name"], "Alex Morgan")
        self.assertEqual(feed.json["items"][0]["recipient_name"], "Sam Taylor")
        self.assertEqual(feed.json["items"][0]["message"], "Thanks for helping me!")

    def test_cannot_send_kudos_to_self_or_with_blank_message(self):
        self.assertEqual(self.send_kudos(recipient_id=1).status_code, 400)
        self.assertEqual(self.send_kudos(message="   ").status_code, 400)

    def test_message_over_500_characters_is_rejected(self):
        response = self.send_kudos(message="x" * 501)
        self.assertEqual(response.status_code, 400)

    def test_same_idempotency_key_does_not_create_a_second_message(self):
        self.assertEqual(self.send_kudos().status_code, 201)
        self.assertEqual(self.send_kudos().status_code, 200)
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) FROM kudos").fetchone()[0]
        self.assertEqual(count, 1)

    def test_non_admin_cannot_moderate_messages(self):
        self.send_kudos()
        response = self.client.post(
            "/api/admin/kudos/1/moderate",
            json={"action": "hide", "reason": "Test"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_hide_message_and_action_is_recorded(self):
        self.send_kudos()
        with self.client.session_transaction() as session:
            session["user_id"] = 4
        response = self.client.post(
            "/api/admin/kudos/1/moderate",
            json={"action": "hide", "reason": "Needs a review"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/kudos").json["items"], [])
        history = self.client.get("/api/admin/kudos/1/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json["events"][0]["action"], "hide")
        self.assertEqual(history.json["events"][0]["reason"], "Needs a review")

    def test_production_mode_rejects_demo_sign_in(self):
        with self.assertRaises(RuntimeError):
            create_app({"APP_ENV": "production", "DEMO_MODE": True})


if __name__ == "__main__":
    unittest.main()
