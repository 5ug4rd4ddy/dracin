# Panduan Deployment DracinLovers (Docker + CloudPanel)

Dokumen ini menjelaskan cara men-deploy aplikasi Flask menggunakan Docker di server yang menggunakan CloudPanel.

## Prasyarat
- Akses **SSH Root** (untuk install Docker).
- Akses **SSH User** (`dracinsubindo`) untuk upload dan menjalankan aplikasi.
- Domain sudah diarahkan ke server.
- Database sudah dibuat di CloudPanel (catat nama database, user, dan password).

---

## Bagian 1: Instalasi Docker (Wajib sebagai ROOT)

Langkah ini hanya perlu dilakukan satu kali saat pertama kali setup server.

1.  Login ke server sebagai **root**:
    ```bash
    ssh root@ip-server-anda
    ```

2.  Jalankan perintah berikut untuk menginstall Docker:
    ```bash
    # Update repository
    apt-get update

    # Install paket pendukung
    apt-get install -y ca-certificates curl gnupg

    # Tambahkan GPG key Docker resmi
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Setup repository Docker
    echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

3.  (PENTING) Berikan izin user `dracinsubindo` untuk menjalankan Docker tanpa sudo:
    ```bash
    usermod -aG docker dracinsubindo
    ```

4.  Keluar dari root:
    ```bash
    exit
    ```

---

## Bagian 2: Setup GitHub Deploy Key (Untuk Private Repo)

Agar server bisa melakukan `git clone` dan `git pull` dari repository private tanpa password, kita perlu menggunakan **SSH Deploy Key**.

1.  Login sebagai user:
    ```bash
    ssh dracinsubindo@ip-server-anda
    ```

2.  Generate SSH Key baru (tekan Enter terus saat diminta passphrase):
    ```bash
    ssh-keygen -t ed25519 -C "server-deployment"
    ```

3.  Tampilkan public key yang baru dibuat:
    ```bash
    cat ~/.ssh/id_ed25519.pub
    ```
    *Copy output yang muncul (dimulai dari `ssh-ed25519` ...)*

4.  Buka Repository GitHub Anda -> **Settings** -> **Deploy keys** -> **Add deploy key**.
    - **Title**: Server CloudPanel (atau nama lain)
    - **Key**: Paste kode yang tadi dicopy.
    - **Allow write access**: Biarkan tidak dicentang (Read-only lebih aman).
    - Klik **Add key**.

5.  Test koneksi dari server:
    ```bash
    ssh -T git@github.com
    ```
    *Ketik `yes` jika ditanya "Are you sure you want to continue connecting?".*
    *Jika berhasil, akan muncul pesan: "Hi username! You've successfully authenticated..."*

---

## Bagian 3: Setup Aplikasi (Sebagai USER)

Lakukan langkah ini sebagai user aplikasi (misal: `dracinsubindo`).

1.  Login ke server sebagai **user**:
    ```bash
    ssh dracinsubindo@ip-server-anda
    ```

2.  Masuk ke direktori aplikasi:
    ```bash
    cd /home/dracinsubindo/htdocs/dracinsubindo.me
    ```
    *(Pastikan folder ini kosong atau hanya berisi file default CloudPanel yang bisa dihapus jika menimpa)*

3.  Clone repository Anda menggunakan **SSH URL**:
    ```bash
    # Hapus file default jika ada
    rm -rf * .git

    # Clone (GANTI username dan nama-repo)
    git clone git@github.com:username/nama-repo.git .
    ```
    *Titik (.) di akhir perintah penting agar file di-clone langsung ke folder saat ini, bukan membuat folder baru.*

4.  Buat file `.env` untuk production:
    ```bash
    nano .env
    ```

5.  Isi `.env` dengan konfigurasi production (sesuaikan database dengan CloudPanel):

    ```ini
    # Ganti secret key dengan random string yang panjang
    SECRET_KEY=ganti_dengan_random_string_panjang_dan_rahasia

    # KONEKSI DATABASE
    # Penting: Jika menggunakan MySQL CloudPanel dari dalam Docker, gunakan IP host (biasanya 172.17.0.1)
    # Format: mysql+pymysql://user:password@172.17.0.1/nama_database
    SQLALCHEMY_DATABASE_URI=mysql+pymysql://nama_user_db:password_db@172.17.0.1/nama_database

    # Google OAuth (Wajib HTTPS)
    GOOGLE_CLIENT_ID=client_id_anda
    GOOGLE_CLIENT_SECRET=client_secret_anda
    
    # Trakteer
    TRAKTEER_WEBHOOK_TOKEN=token_anda
    ```
    *Catatan: IP `172.17.0.1` adalah IP gateway default Docker untuk mengakses service di host (MySQL CloudPanel).*

---

## Bagian 4: Menjalankan Aplikasi

Masih sebagai **user** (`dracinsubindo`) di folder `/home/dracinsubindo/htdocs/dracinsubindo.me`:

1.  Build dan jalankan container:
    ```bash
    docker compose up -d --build
    ```

2.  Cek apakah container berjalan:
    ```bash
    docker compose ps
    ```
    *Status harus `Up`.*

3.  Jalankan migrasi database (untuk membuat tabel):
    ```bash
    docker compose exec web flask db upgrade
    ```
    *Jika error "Can't connect to MySQL server", pastikan user database di CloudPanel diizinkan akses dari `%` atau IP Docker, dan password benar.*

---

## Bagian 4: Konfigurasi CloudPanel (Reverse Proxy)

Agar website bisa diakses publik via HTTPS:

1.  Login ke Dashboard CloudPanel.
2.  Masuk ke menu **Sites** -> **Add Site**.
3.  Pilih **Create a Docker Proxy Site**.
4.  Isi form:
    - **Domain Name**: `dracinsubindo.me`
    - **Proxy Pass**: `http://127.0.0.1:5002`
5.  Klik **Create**.
6.  Masuk ke tab **SSL/TLS**, aktifkan Let's Encrypt untuk HTTPS.

---

## Maintenance & Update

Setiap kali Anda mengubah kode (push ke git atau upload file baru):

1.  Login SSH sebagai user.
2.  Masuk direktori:
    ```bash
    cd /home/dracinsubindo/htdocs/dracinsubindo.me
    ```
3.  Pull kode terbaru (jika pakai git) atau upload file baru.
4.  Rebuild container:
    ```bash
    docker compose up -d --build
    ```

**Melihat Logs Error:**
```bash
docker compose logs -f
```

**Restart Aplikasi:**
```bash
docker compose restart
```
