# Coolify-Ready Router Reboot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the router-reboot script deployable on the local Coolify server (`http://192.168.0.5:8000`) with a Discord message after every run.

**Architecture:** Deployed as Coolify Docker Compose app (`docker-compose.yaml`, with CPU/memory/pids limits). Container idles (`sleep infinity`); a Coolify Scheduled Task (`0 3 * * *`) execs `python main.py`. `main.py` posts a Discord message on success and failure and exits 1 on failure. Secrets live only in Coolify env vars.

**Tech Stack:** Python 3.12, selenium, stdlib `urllib`/`unittest`, Docker, Coolify (via `coolify` MCP).

**Spec:** chat conversation 2026-10-31 (no spec doc; decisions below are the spec).

## Global Constraints

- Notify on EVERY run: success and failure.
- `DISCORD_WEBHOOK_URL` is optional; unset → skip notify, no error.
- Webhook URL, router password: never written to repo, image, or logs. Env vars only.
- No new third-party dependency (notify uses stdlib `urllib`).
- Failure → process exit code 1. Success → 0.
- Never run `main.py` against the real router (reboots it). Tests mock everything.
- k8s manifests (`router-reboot-cronjob.yaml`, `router-reboot-secret.yaml`) untouched.
- Base image `python:3.12-slim` (agent's call; 3.9 is EOL).

## Review Focus

- Webhook down / 4xx / timeout → notify must not raise; run exit code unchanged.
- `DISCORD_WEBHOOK_URL` unset → no network call.
- Exception text containing the router password or webhook URL → must not be posted/logged verbatim (message limited to exception class + str(e); URL never in message).
- Discord 2000-char content limit → truncate message.
- Failure after reboot click partially done → still reports FAILED, exit 1.

---

### Task 1: Notify + exit codes in main.py

**Files:**
- Modify: `main.py`
- Create: `tests/test_notify.py`

**Interfaces:**
- Produces: `notify(message: str) -> None` in `main.py` (reads `DISCORD_WEBHOOK_URL` at call time; never raises); `reboot_router() -> bool` (True on success).

- [ ] **Step 1: Write failing tests** in `tests/test_notify.py` (`unittest`, set `ROUTER_PASSWORD=x` in `os.environ` before `import main`; patch `main.urllib.request.urlopen`):
  - `test_notify_skips_when_unset`: env var unset → `urlopen` not called.
  - `test_notify_posts_json_content`: env set → `urlopen` called once; request body JSON has key `content` equal to message; `Content-Type: application/json`; also a `User-Agent` header set (Discord rejects the default Python UA with 403).
  - `test_notify_swallows_errors`: `urlopen` raises `OSError` → `notify("x")` returns None.
  - `test_notify_truncates`: 3000-char message → posted `content` length ≤ 2000.
  - `test_reboot_returns_false_on_error`: patch `main.webdriver.Chrome` to raise → `reboot_router()` is False and `urlopen` payload starts with `❌`.
- [ ] **Step 2: Run** `python -m unittest tests.test_notify -v` (needs `tests/__init__.py`, empty). Expected: FAIL (`notify` missing).
- [ ] **Step 3: Implement** in `main.py`: `import json, sys, urllib.request`; `notify` as above (timeout 10s, errors printed without the URL); `reboot_router` returns True/False and calls `notify("✅ Router reboot triggered")` / `notify(f"❌ Router reboot FAILED: {type(e).__name__}: {e}")` (exception branch); `__main__` block: `sys.exit(0 if reboot_router() else 1)`. Keep existing selenium flow unchanged.
- [ ] **Step 4: Run** same command. Expected: all PASS.
- [ ] **Step 5: Commit** `git add main.py tests/` → `feat: discord notify and exit code on failure`

### Task 2: Container + docs

**Files:**
- Modify: `Dockerfile`, `README.md`
- Create: `.env.example`

**Interfaces:**
- Consumes: Task 1 `main.py` behavior (exit code, `DISCORD_WEBHOOK_URL`).

- [ ] **Step 1: Dockerfile**: `FROM python:3.12-slim`; keep Chrome install; replace `CMD` with `CMD ["sleep", "infinity"]`; add a comment that Coolify Scheduled Task runs `python /app/main.py`.
- [ ] **Step 2a: local `.env` for testing** (gitignored, not committed): create `.env` from `.env.example` with DUMMY values only (`ROUTER_URL=https://127.0.0.1`, `ROUTER_PASSWORD=dummy`, `DISCORD_WEBHOOK_URL` empty). Never real creds or the real webhook; a dummy `ROUTER_URL` makes accidental real runs harmless. Verify `git check-ignore .env` prints `.env` and `git status` does not list it.
- [ ] **Step 2: `.env.example`** with `ROUTER_URL`, `ROUTER_USERNAME`, `ROUTER_PASSWORD`, `DISCORD_WEBHOOK_URL`, all placeholder values.
- [ ] **Step 3: `docker-compose.yaml`** (Coolify "Docker Compose" build pack): single service `router-reboot`, `build: .`, `restart: unless-stopped`, `init: true`, `shm_size: 256m`, env passthrough by name only (`ROUTER_URL`, `ROUTER_USERNAME`, `ROUTER_PASSWORD`, `DISCORD_WEBHOOK_URL` as `${VAR}` / `${VAR:?}` for required ones; no values, no `.env` file mounted), no ports. Resource limits (agent's guess, user to confirm): `mem_limit: 1g`, `cpus: 1.0`, `pids_limit: 256` (plain compose keys, honored by Coolify without swarm). `deploy.resources` not used.
- [ ] **Step 4: README rewrite** (`README.md`, replace whole file; target ≤ ~70 lines; keep `assets/image.png`; keep MIT + Contributing as 1-liners). Standard structure, in order:
  1. Title + one-line description (KAON/Telekom router, Selenium, daily reboot, Discord status).
  2. Features (3-4 bullets: headless Chrome reboot, Discord notify every run, exit code 1 on failure, runs on Coolify/Docker/k8s).
  3. Configuration: env var table (`ROUTER_URL` default `https://192.168.0.1`, `ROUTER_USERNAME` default `admin`, `ROUTER_PASSWORD` required/secret, `DISCORD_WEBHOOK_URL` optional/secret).
  4. Usage: Local (`pip install -r requirements.txt`, `.env` from `.env.example`, `python main.py` + warning it reboots the real router); Docker Compose; tests (`python -m unittest`).
  5. Deployment: Coolify (primary): Docker Compose build pack, env vars as secrets, Scheduled Task `router-reboot` / `python /app/main.py` / `0 3 * * *`, resource limits table; Kubernetes (legacy): 1-2 lines pointing at `router-reboot-cronjob.yaml`.
  6. Contributing, License (MIT).
  Remove: pyenv/direnv scratch notes, base64 password instruction (wrong: password is plain env var), `GITHUB_TOKEN`, GHCR package-linking walkthrough, duplicate "runs headlessly 🚀" lines, `tools/` ChromeDriver step (webdriver-manager/Selenium Manager handles it in Docker; mention `tools/` only as optional local helper).
- [ ] **Step 5: Verify compose** `docker compose config` with dummy env (`ROUTER_PASSWORD=x ROUTER_USERNAME=x`). Expected: valid, limits shown. Then `docker compose build`. Expected: success (needs Docker running; if unavailable, say so, do not claim pass).
- [ ] **Step 6: Verify entrypoint** `docker compose run --rm router-reboot python -c "import selenium"` Expected: exit 0. Do NOT run `main.py`.
- [ ] **Step 7: Commit** `git add Dockerfile docker-compose.yaml .env.example README.md` → `feat: coolify-ready compose with resource limits`

### Task 3: Coolify config via MCP (blocked until MCP loaded in this project)

**Prerequisite:** `coolify` MCP added to this project (`claude mcp add coolify -e COOLIFY_BASE_URL=http://192.168.0.5:8000 -e COOLIFY_ACCESS_TOKEN=<token> -- npx -y @masonator/coolify-mcp`) and session restarted. Do not print the token.

**Open (user):** Coolify app source. If the app does not exist yet, user picks git repo vs. registry image; agent does not guess.

- [ ] **Step 1:** List Coolify applications via MCP; locate/create the reboot app (confirm with user before creating).
- [ ] **Step 2:** Set env vars via MCP: `ROUTER_URL`, `ROUTER_USERNAME`, `ROUTER_PASSWORD`, `DISCORD_WEBHOOK_URL` (runtime only, not build-time). Values supplied by user; confirm before writing the secrets.
- [ ] **Step 3:** Create Scheduled Task: service `router-reboot`, command `python /app/main.py`, cron `0 3 * * *`. Confirm before creating (it reboots the real router).
- [ ] **Step 4:** Deploy. Expected: container running, env vars listed with secrets masked.
- [ ] **Step 5:** Ask user before any live trigger of the task (reboots router; posts to Discord).
