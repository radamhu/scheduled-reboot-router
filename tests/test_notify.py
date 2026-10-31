import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("ROUTER_PASSWORD", "x")

import main  # noqa: E402

URL = "https://discord.example/api/webhooks/secret-token"


class NotifyTests(unittest.TestCase):
    def test_notify_skips_when_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "DISCORD_WEBHOOK_URL"}
        with patch.dict(os.environ, env, clear=True), \
                patch("main.urllib.request.urlopen") as uo:
            main.notify("hi")
            uo.assert_not_called()

    def test_notify_posts_json_content(self):
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": URL}), \
                patch("main.urllib.request.urlopen") as uo:
            main.notify("hello")
            uo.assert_called_once()
            req = uo.call_args[0][0]
            self.assertEqual(json.loads(req.data)["content"], "hello")
            self.assertEqual(req.get_header("Content-type"), "application/json")
            self.assertTrue(req.get_header("User-agent"))

    def test_notify_swallows_errors(self):
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": URL}), \
                patch("main.urllib.request.urlopen", side_effect=OSError("boom")):
            self.assertIsNone(main.notify("x"))

    def test_notify_truncates(self):
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": URL}), \
                patch("main.urllib.request.urlopen") as uo:
            main.notify("a" * 3000)
            req = uo.call_args[0][0]
            self.assertLessEqual(len(json.loads(req.data)["content"]), 2000)

    def test_reboot_returns_false_on_error(self):
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": URL}), \
                patch("main.urllib.request.urlopen") as uo, \
                patch("main.webdriver.Chrome", side_effect=RuntimeError("no chrome")):
            self.assertFalse(main.reboot_router())
            req = uo.call_args[0][0]
            self.assertTrue(json.loads(req.data)["content"].startswith("❌"))


if __name__ == "__main__":
    unittest.main()
