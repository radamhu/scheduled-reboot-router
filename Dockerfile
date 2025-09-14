FROM python:3.9-slim

WORKDIR /app

# Install Chrome and dependencies
RUN apt-get update && apt-get install -y wget unzip \
    && wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/google-chrome.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/google-chrome.deb

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# COPY chromedriver.linux .
# RUN chmod +x chromedriver.linux
COPY main.py .

CMD ["python", "main.py"]
