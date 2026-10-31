import json
import logging
import os
import re
import sys
import time
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

log = logging.getLogger("reboot")

STEP_TIMEOUT_MS = 15_000
ARTIFACT_DIR = "/tmp/reboot-artifacts"
DUMP_TEXT_CHARS = 3000
DUMP_MAX_ELEMENTS = 80

# Absolute XPaths carried over from the Selenium version: the router UI has no stable ids.
CONFIRM_1_XPATH = "xpath=/html/body/section/section/div/div[1]/div/section/article/div/div/section[2]/div/table[1]/div/div/p/tbody/tr/th/div/button"
CONFIRM_2_XPATH = "xpath=/html/body/section/section/div/div[1]/div/section/article/div/div/section[2]/section/div/div/div[2]/div[2]/button[1]"
REBOOT_BUTTON = ':is(button, [role=button], input[type=button]):has-text("Reboot")'

LIST_ELEMENTS_JS = """
() => [...document.querySelectorAll('button, a, [role=button], input[type=button], input[type=submit]')]
  .filter(e => e.offsetParent !== null)
  .map(e => ({
    tag: e.tagName.toLowerCase(),
    text: (e.innerText || e.value || '').trim().slice(0, 60),
    id: e.id || '',
    cls: (typeof e.className === 'string' ? e.className : '').slice(0, 60),
    aria: e.getAttribute('aria-label') || '',
  }))
"""


class ConfigError(Exception):
    pass


@dataclass
class Config:
    url: str
    username: str
    password: str
    dry_run: bool

    @classmethod
    def from_env(cls):
        username = os.getenv("ROUTER_USERNAME", "admin")
        password = os.getenv("ROUTER_PASSWORD")
        if not username or not password:
            raise ConfigError("Missing required environment variables: ROUTER_USERNAME and ROUTER_PASSWORD")
        return cls(
            url=os.getenv("ROUTER_URL", "https://192.168.0.1").rstrip("/"),
            username=username,
            password=password,
            dry_run=os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes"),
        )


class Redactor(logging.Filter):
    """Masks secrets in every log line so the password/webhook token never reach Coolify logs."""

    def __init__(self, secrets):
        super().__init__()
        self.secrets = [s for s in secrets if s]

    def filter(self, record):
        msg = record.getMessage()
        for secret in self.secrets:
            msg = msg.replace(secret, "***")
        record.msg, record.args = msg, None
        return True


def setup_logging(level, secrets):
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", "%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    handler.addFilter(Redactor(secrets))
    log.handlers[:] = [handler]
    log.setLevel(level.upper() if level.upper() in logging._nameToLevel else "INFO")
    log.propagate = False


def notify(message):
    """Post message to Discord webhook if DISCORD_WEBHOOK_URL is set. Never raises."""
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return
    try:
        body = json.dumps({"content": message[:2000]}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "reboot-router/1.0",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        log.info("discord notified")
    except Exception as e:
        # Never log the URL (contains the webhook token)
        log.warning("discord notify failed: %s", type(e).__name__)


@contextmanager
def step(name):
    """Log start/duration/result of a step; tag any exception with the step name."""
    log.info("▶ %s", name)
    started = time.monotonic()
    try:
        yield
    except Exception as e:
        if not hasattr(e, "step"):
            e.step = name
        log.error("✖ %s failed after %.1fs: %s", name, time.monotonic() - started, _short(e))
        raise
    log.info("✔ %s (%.1fs)", name, time.monotonic() - started)


def _short(exc):
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0][:300] or type(exc).__name__


def attach_listeners(page):
    page.on("framenavigated", lambda f: log.info("navigated: %s", f.url) if f == page.main_frame else None)
    page.on("console", lambda m: log.log(
        logging.WARNING if m.type in ("error", "warning") else logging.DEBUG, "browser console %s: %s", m.type, m.text[:300]))
    page.on("pageerror", lambda e: log.warning("browser pageerror: %s", _short(e)))
    page.on("requestfailed", lambda r: log.warning("request failed: %s %s (%s)", r.method, r.url, r.failure))
    page.on("response", lambda r: log.warning("http %s: %s %s", r.status, r.request.method, r.url) if r.status >= 400 else None)


def dump_page(page, tag="failure"):
    """Log everything needed to rebuild selectors without access to the router UI. Never raises."""
    log.info("---- page dump (%s) ----", tag)
    try:
        log.info("url: %s", page.url)
        log.info("title: %s", page.title())
    except Exception as e:
        log.warning("dump url/title failed: %s", _short(e))
    try:
        elements = page.evaluate(LIST_ELEMENTS_JS)
        log.info("visible clickables: %d", len(elements))
        for el in elements[:DUMP_MAX_ELEMENTS]:
            log.info("  <%(tag)s> text=%(text)r id=%(id)r class=%(cls)r aria=%(aria)r", el)
    except Exception as e:
        log.warning("dump elements failed: %s", _short(e))
    try:
        text = " | ".join(page.inner_text("body").split())
        log.info("body text: %s", text[:DUMP_TEXT_CHARS])
    except Exception as e:
        log.warning("dump body text failed: %s", _short(e))
    try:
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        page.screenshot(path=f"{ARTIFACT_DIR}/{tag}.png", full_page=True)
        with open(f"{ARTIFACT_DIR}/{tag}.html", "w", encoding="utf-8") as fh:
            fh.write(page.content())
        log.info("saved %s/%s.png and .html", ARTIFACT_DIR, tag)
    except Exception as e:
        log.warning("dump artifacts failed: %s", _short(e))
    log.info("---- end page dump ----")


def login(page, cfg):
    with step("open router"):
        page.goto(cfg.url)
    username = page.get_by_placeholder(re.compile("Username", re.I))
    with step("enter credentials"):
        username.fill(cfg.username)
        page.get_by_placeholder(re.compile("Password", re.I)).fill(cfg.password)
    with step("submit login"):
        page.locator("button[type=submit]").click()
        username.wait_for(state="hidden")  # login form disappears once logged in


def open_admin_page(page, cfg):
    with step("open administration page"):
        page.goto(cfg.url + "/#/home/administration")
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            log.debug("networkidle not reached, continuing")


def click_through_reboot(page):
    with step("click Reboot"):
        page.locator(REBOOT_BUTTON).first.click()
    with step("confirm 1"):
        page.locator(CONFIRM_1_XPATH).click()
    with step("confirm 2"):
        page.locator(CONFIRM_2_XPATH).click()


def _run(browser, cfg):
    context = browser.new_context(ignore_https_errors=True)  # router uses a self-signed cert
    context.set_default_timeout(STEP_TIMEOUT_MS)
    page = context.new_page()
    attach_listeners(page)
    try:
        login(page, cfg)
        open_admin_page(page, cfg)
        if cfg.dry_run:
            log.info("DRY_RUN set: skipping reboot clicks")
            dump_page(page, "dry-run")
            return
        click_through_reboot(page)
    except Exception:
        dump_page(page)
        raise
    finally:
        context.close()


def reboot_router(cfg):
    """Returns True on success. Notifies Discord on failure or reboot; never raises."""
    try:
        with sync_playwright() as pw:
            with step("launch browser"):
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                log.info("chromium %s", browser.version)
            try:
                _run(browser, cfg)
            finally:
                browser.close()
    except Exception as e:
        failed = getattr(e, "step", "unknown")
        log.error("❌ reboot FAILED at step '%s': %s", failed, _short(e))
        log.debug("traceback", exc_info=True)
        notify(f"❌ Router reboot FAILED at '{failed}': {type(e).__name__}: {_short(e)}")
        return False
    if cfg.dry_run:
        log.info("✅ dry run complete, router NOT rebooted")
    else:
        log.info("✅ router reboot initiated")
        notify("✅ Router reboot triggered")
    return True


def main():
    load_dotenv()
    run_id = uuid.uuid4().hex[:8]
    setup_logging(os.getenv("LOG_LEVEL", "INFO"),
                  [os.getenv("ROUTER_PASSWORD"), os.getenv("DISCORD_WEBHOOK_URL")])
    started = time.monotonic()
    log.info("run %s start (python %s)", run_id, sys.version.split()[0])
    try:
        cfg = Config.from_env()
    except ConfigError as e:
        log.error("config error: %s", e)
        notify(f"❌ Router reboot not started: {e}")
        return 2
    log.info("config: url=%s user=%s password=set webhook=%s dry_run=%s",
             cfg.url, cfg.username, "set" if os.getenv("DISCORD_WEBHOOK_URL") else "unset", cfg.dry_run)
    ok = reboot_router(cfg)
    log.info("run %s end status=%s duration=%.1fs", run_id, "ok" if ok else "failed", time.monotonic() - started)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
