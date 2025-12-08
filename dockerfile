FROM python:3.11-slim

WORKDIR /app

# Install system deps only if needed
# RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# If your Flask app is in app.py and Flask instance is named "app":
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8001", "app:app"]
