FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy FTP server code
COPY server.py .
COPY ../.env.example .env

# Create upload directory -- check constants.py for the dir
RUN mkdir -p data/ftp_uploads

# Expose FTP port
EXPOSE 2121

# Expose passive mode port range (optional)
EXPOSE 60000-60100

# Run FTP server
CMD ["python3", "server.py"]
