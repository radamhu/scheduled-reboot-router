import io
import json
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import main

URL = "https://discord.example/api/webhooks/secret-token"
CFG = main.Config(url="https://router", username="admin", password="pw", dry_run=False)


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


class RebootTests(unittest.TestCase):
    def test_reboot_returns_false_and_notifies_on_error(self):
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": URL}), \
                patch("main.urllib.request.urlopen") as uo, \
                patch("main.sync_playwright", side_effect=RuntimeError("no browser")):
            self.assertFalse(main.reboot_router(CFG))
            content = json.loads(uo.call_args[0][0].data)["content"]
            self.assertTrue(content.startswith("❌"))

    def test_failure_message_names_the_step(self):
        pw = MagicMock()
        pw.__enter__.return_value.chromium.launch.side_effect = RuntimeError("boom")
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": URL}), \
                patch("main.urllib.request.urlopen") as uo, \
                patch("main.sync_playwright", return_value=pw):
            self.assertFalse(main.reboot_router(CFG))
            self.assertIn("launch browser", json.loads(uo.call_args[0][0].data)["content"])


class StepTests(unittest.TestCase):
    def test_step_tags_exception_with_first_step_name(self):
        with self.assertRaises(ValueError) as ctx:
            with main.step("outer"):
                with main.step("inner"):
                    raise ValueError("x")
        self.assertEqual(ctx.exception.step, "inner")


class ConfigTests(unittest.TestCase):
    def test_missing_password_raises(self):
        env = {k: v for k, v in os.environ.items() if k != "ROUTER_PASSWORD"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(main.ConfigError):
                main.Config.from_env()

    def test_defaults_and_dry_run(self):
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "p", "DRY_RUN": "1", "ROUTER_URL": "https://r/"}, clear=True):
            cfg = main.Config.from_env()
        self.assertEqual((cfg.username, cfg.url, cfg.dry_run), ("admin", "https://r", True))


class LoggingTests(unittest.TestCase):
    def test_secrets_are_redacted(self):
        stream = io.StringIO()
        with patch("main.sys.stdout", stream):
            main.setup_logging("INFO", ["hunter2", URL])
            main.log.info("login with hunter2 to %s", URL)
        out = stream.getvalue()
        self.assertNotIn("hunter2", out)
        self.assertNotIn("secret-token", out)
        self.assertIn("***", out)

    def tearDown(self):
        main.log.handlers[:] = []


class DumpTests(unittest.TestCase):
    def test_dump_page_never_raises_and_logs_elements(self):
        page = MagicMock()
        page.evaluate.return_value = [{"tag": "button", "text": "Reboot", "id": "", "cls": "btn", "aria": ""}]
        page.inner_text.return_value = "Administration  Reboot"
        page.screenshot.side_effect = OSError("disk")
        with self.assertLogs("reboot", level="INFO") as logs:
            main.dump_page(page, "t")
        joined = "\n".join(logs.output)
        self.assertIn("text='Reboot'", joined)
        self.assertIn("dump artifacts failed", joined)


if __name__ == "__main__":
    unittest.main()
