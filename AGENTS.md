# scheduled-reboot-router

Selenium script reboots KAON/Telekom home router. Runs as k8s CronJob (daily 03:00, ns `tools`).

## Layout
- `main.py` — headless Chrome, login, navigate to reboot submenu, click Reboot
- `Dockerfile` — python:3.9-slim + Chrome; image `ghcr.io/<user>/fluffy-fortnight/reboot-router`
- `router-reboot-cronjob.yaml`, `router-reboot-secret.yaml` — k8s manifests
- `tools/` — ChromeDriver install scripts (local dev)
- `requirements.txt` — selenium, webdriver-manager, python-dotenv

## Run
- Local: `.env` with `ROUTER_URL`, `ROUTER_USERNAME`, `ROUTER_PASSWORD`, then `python main.py`
- Build: `docker build -t ghcr.io/<user>/fluffy-fortnight/reboot-router .`
- Deploy: `kubectl apply -f router-reboot-cronjob.yaml`
- No tests, no linter configured

## Don'ts
- never run `main.py` casually: reboots the real router
- never commit `.env` or real creds in `router-reboot-secret.yaml`
- don't add `.env` to Docker image (prod uses k8s Secret env vars)
