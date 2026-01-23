#!/bin/bash

# Script Deployment Otomatis dengan Downtime Minimal

echo "🚀 Memulai Deployment..."

# 1. Pull kode terbaru
echo "📥 Pulling latest code..."
git pull origin main

# 2. Build image BARU (Aplikasi masih jalan menggunakan image LAMA)
# Ini adalah kunci untuk meminimalkan downtime. Kita build dulu sampai selesai.
echo "🔨 Building new image..."
docker compose build

# 3. Ganti container (Downtime terjadi di sini, hanya beberapa detik)
echo "🔄 Recreating containers (Web & Bot)..."
docker compose up -d

# 4. Jalankan Migrasi Database Otomatis
echo "🗄️ Running database migrations..."
docker compose exec -T web flask db upgrade

# 5. Hapus image lama yang tidak terpakai (bersih-bersih)
echo "🧹 Cleaning up old images..."
docker image prune -f

echo "✅ Deployment Selesai!"
