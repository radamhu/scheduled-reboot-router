# scheduled-reboot-router

Playwright script reboots KAON/Telekom home router. Runs on Coolify (idle container + Scheduled Task `python /app/main.py`, daily 05:00); k8s CronJob manifests are legacy.

## Layout
- `main.py` — headless Chromium (Playwright), step logging, login, Reboot tab, confirm clicks; `DRY_RUN=1` logs in and dumps page only, never clicks confirm
- `Dockerfile` — `mcr.microsoft.com/playwright/python` (tag must match `playwright` pin in requirements)
- `docker-compose.yaml` — Coolify build source (service `router-reboot`)
- `router-reboot-cronjob.yaml`, `router-reboot-secret.yaml` — k8s manifests
- `requirements.txt` — playwright (pinned), python-dotenv

## Run
- Local: `.env` with `ROUTER_URL`, `ROUTER_USERNAME`, `ROUTER_PASSWORD`; `pip install -r requirements.txt && playwright install chromium`; safe check: `DRY_RUN=1 python main.py`
- Tests: `python -m unittest discover -s tests -t .`
- Build: `docker build -t reboot-router .`
- Deploy: push to `main`, redeploy Coolify app (env vars live in Coolify); legacy: `kubectl apply -f router-reboot-cronjob.yaml`
- No linter configured

## Don'ts
- never run `main.py` casually: reboots the real router
- never commit `.env` or real creds in `router-reboot-secret.yaml`
- don't add `.env` to Docker image (prod uses Coolify env vars / k8s Secret)
