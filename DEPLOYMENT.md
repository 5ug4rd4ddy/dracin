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
    # Karena kita sudah set extra_hosts di docker-compose.yml, kita bisa pakai host.docker.internal
    # Format: mysql+pymysql://user:password@host.docker.internal/nama_database
    SQLALCHEMY_DATABASE_URI=mysql+pymysql://nama_user_db:password_db@host.docker.internal/nama_database

    # PENTING:
    # Di CloudPanel -> Databases -> User Management:
    # Pastikan user database diizinkan connect dari "Any" (%) atau IP Docker.
    # Jika defaultnya "localhost", koneksi dari Docker akan DITOLAK.

    # Google OAuth (Wajib HTTPS)
    GOOGLE_CLIENT_ID=client_id_anda
    GOOGLE_CLIENT_SECRET=client_secret_anda
    
    # Trakteer
    TRAKTEER_WEBHOOK_TOKEN=token_anda
    ```
    *Catatan: `host.docker.internal` akan otomatis diarahkan ke IP host server.*

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

## Bagian 5: Konfigurasi CloudPanel (Reverse Proxy)

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

## Maintenance & Update (Zero-Downtime Strategy)

### Apakah ada Downtime?
Ya, dengan cara biasa (`docker compose up -d --build`), downtime terjadi selama proses build + restart (bisa 1-2 menit).
Namun, kita bisa meminimalkan downtime menjadi **hanya beberapa detik** (hanya saat restart container) dengan strategi **Build-First**.

### Cara Deploy Cepat (Recommended)
Saya telah membuatkan script `deploy.sh` untuk mengotomatisasi proses ini.

1.  Login ke server.
2.  Masuk ke folder aplikasi.
3.  Berikan izin eksekusi script (hanya sekali):
    ```bash
    chmod +x deploy.sh
    ```
4.  Jalankan deployment:
    ```bash
    ./deploy.sh
    ```

**Apa yang dilakukan script ini?**
1.  `git pull` (Ambil kode baru).
2.  `docker compose build` (Build image baru di background **sementara website masih hidup**).
3.  `docker compose up -d` (Matikan container lama & nyalakan yang baru -> Downtime ~3 detik).
4.  `docker image prune` (Hapus sampah image lama).

---

### FAQ: Bisakah 100% Zero-Downtime?
Untuk mencapai **benar-benar 0 detik** downtime, arsitekturnya harus diubah menjadi **Blue-Green Deployment**:
1.  Perlu menjalankan 2 container sekaligus.
2.  Perlu Load Balancer internal (Nginx) di depan container.
3.  Kompleksitasnya tinggi dan memakan resource RAM 2x lipat.

**Saran:** Untuk skala saat ini, downtime 3 detik menggunakan `deploy.sh` sudah sangat ideal dan tidak mengganggu user.

---

### Troubleshooting

**1. Error: permission denied while trying to connect to the Docker daemon socket**
Ini terjadi karena user Anda belum masuk ke grup `docker`.

**Solusi:**
1.  Jalankan perintah ini (membutuhkan akses root atau sudo):
    ```bash
    sudo usermod -aG docker $USER
    ```
2.  **PENTING:** Anda harus **LOGOUT** dari SSH dan **LOGIN KEMBALI** agar perubahan grup diterapkan.
3.  Cek apakah sudah berhasil dengan mengetik `groups`. Harus ada `docker` di outputnya.

**2. Error: Can't connect to MySQL server**
Pastikan di CloudPanel user database diizinkan connect dari IP manapun (`%`) atau IP gateway Docker.
