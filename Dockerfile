# Gunakan image Python official yang ringan
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Mencegah Python menulis file .pyc
# PYTHONUNBUFFERED: Memastikan log Python langsung keluar (penting untuk Docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install dependencies sistem yang mungkin dibutuhkan (misal untuk PostgreSQL atau Pillow)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements terlebih dahulu untuk memanfaatkan cache layer Docker
COPY requirements.txt .

# Install dependencies Python
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy seluruh kode aplikasi
COPY . .

# Buat direktori instance jika belum ada (untuk SQLite jika dipakai)
RUN mkdir -p instance

# Expose port yang digunakan Gunicorn
EXPOSE 5002

# Command untuk menjalankan aplikasi
CMD ["gunicorn", "-c", "gunicorn_config.py", "run:app"]
