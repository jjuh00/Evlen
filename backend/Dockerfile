FROM python:3.12-slim

WORKDIR /app

# Install dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make the entry point script executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs generate_secret.py and then starts uvicorn
ENTRYPOINT ["/app/entrypoint.sh"]