# Image tag must match the playwright pin in requirements.txt (browsers are preinstalled for that version)
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Coolify Scheduled Task runs: python /app/main.py
CMD ["sleep", "infinity"]
