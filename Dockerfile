FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Dependências de sistema + Google Chrome (necessário pro modo UC do SeleniumBase)
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg unzip curl \
        libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 \
        libxss1 libxtst6 fonts-liberation xdg-utils ca-certificates \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn seleniumbase

WORKDIR /app
COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
