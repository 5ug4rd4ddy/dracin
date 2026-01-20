# Product Requirement Document (PRD)

**Project Name:** C-Drama Stream Platform
**Tech Stack:** Python (Flask), MySQL, SQLAlchemy, HTML/TailwindCSS (Frontend), Google OAuth.

## 1. Project Overview

Platform berbasis web untuk streaming Drama China. Platform ini menggunakan model *Freemium*, di mana pengguna dapat menonton beberapa episode awal secara gratis, namun harus berlangganan untuk membuka episode terkunci. Fokus utama adalah kemudahan akses pengguna (Google Login) dan fleksibilitas manajemen bagi Admin.

## 2. User Roles (Peran Pengguna)

### A. Customer (User)

* **Authentication:** Login menggunakan akun Google (OAuth).
* **Viewing:**
* Menonton episode dengan status `is_free = 1` tanpa batasan (bisa di-set login optional atau required).
* Melihat daftar film dan detail film.


* **Interaction:** Menambahkan film ke daftar "Favorite".
* **Subscription:**
* Melihat paket berlangganan.
* Melakukan pembayaran (via Trakteer - *Logic integrasi dibahas terpisah*).
* Membuka episode terkunci (`is_free = 0`) jika memiliki status berlangganan aktif.



### B. Admin

* **Dashboard:** Melihat ringkasan (Total user, Total active subs, Total movies).
* **Management:**
* CRUD Movies (Create, Read, Update, Delete).
* CRUD Episodes (Upload link video, set judul, set `is_free`).
* CRUD Subscription Plans (Mengatur durasi dan harga paket).


* **Transactions:** Melihat riwayat pembayaran user.
* **Settings:** Pengaturan SEO (Meta Title, Description, Keywords) dan konfigurasi dasar situs.

---

## 3. Database Schema Design (MySQL)

Selain tabel `movies` dan `episodes` yang sudah ada, kita perlu menambahkan tabel untuk Users, Subscription Plans, Transactions, dan Favorites.

### A. Tabel Utama (Content)

**1. `movies` (sesuai existing)**

**2. `episodes` (sesuai existing)**

### B. Tabel User & Transaksi

**3. `users**`
Menyimpan data user dari Google dan status langganan.

```sql
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL UNIQUE,
  `name` varchar(255),
  `google_id` varchar(255), -- ID unik dari Google
  `profile_pic` varchar(255),
  `role` enum('admin', 'customer') DEFAULT 'customer',
  `subscription_end_date` datetime DEFAULT NULL, -- Kunci akses premium
  `created_at` timestamp DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
);

```

**4. `subscription_plans**`
Tabel dinamis agar admin bisa membuat paket sesuka hati.

```sql
CREATE TABLE `subscription_plans` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL, -- Contoh: "Paket 7 Hari", "Paket Sultan"
  `price` decimal(10, 2) NOT NULL,
  `duration_days` int(11) NOT NULL, -- Durasi dalam hari (misal: 30, 365, 36500 untuk lifetime)
  `is_active` tinyint(1) DEFAULT 1, -- Untuk menyembunyikan paket tanpa menghapusnya
  PRIMARY KEY (`id`)
);

```

**5. `transactions**`
Mencatat history pembayaran Trakteer.

```sql
CREATE TABLE `transactions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `plan_id` int(11),
  `amount` decimal(10, 2),
  `status` enum('pending', 'paid', 'failed') DEFAULT 'pending',
  `payment_proof` text, -- Bisa URL bukti transfer atau Trakteer ID
  `created_at` timestamp DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
);

```

**6. `favorites**`

```sql
CREATE TABLE `favorites` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `movie_id` int(11) NOT NULL,
  `created_at` timestamp DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_fav` (`user_id`, `movie_id`), -- Mencegah duplikat
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`)
);

```

---

## 4. Functional Specifications & Logic

### A. Authentication & Security

* **Library:** `Authlib` (untuk Google OAuth) + `Flask-Login`.
* **Admin Access:** Admin harus ditandai di database (`role='admin'`). Halaman admin dilindungi middleware/decorator `@admin_required`.
* **Security Measures:**
* **CSRF Protection:** Menggunakan `Flask-WTF` untuk semua form (termasuk form di admin).
* **Secure Session:** Cookie session harus dienkripsi (`SECRET_KEY` yang kuat).
* **XSS Protection:** Jinja2 templating engine secara otomatis melakukan escaping, namun input di Admin (seperti deskripsi film) mungkin butuh sanitizer jika menggunakan Rich Text Editor.



### B. Video Player Logic

Logic untuk menentukan apakah user boleh menonton:

1. User klik episode.
2. Backend cek `episodes.is_free`.
* **Jika 1 (Gratis):** Render halaman player.
* **Jika 0 (Berbayar):**
* Cek apakah user login? Jika tidak -> Redirect ke Login.
* Cek `users.subscription_end_date`.
* Apakah `subscription_end_date` > `current_timestamp`?
* **Ya:** Render halaman player.
* **Tidak:** Tampilkan pesan "Video Terkunci. Silakan Berlangganan" + Icon Gembok.







### C. Subscription Logic (Admin Config)

Admin dapat membuat paket dengan logika hari:

* 1 Hari = `duration_days: 1`
* 1 Bulan = `duration_days: 30`
* Lifetime = `duration_days: 36500` (100 tahun)

Saat transaksi sukses (callback dari Trakteer/Manual approve), sistem akan mengupdate `users.subscription_end_date`:

* *Rumus:* `New Expiry = MAX(Current Now, Current Expiry) + Plan Duration`.

---

## 5. System Architecture (Flask Structure)

Struktur folder yang disarankan untuk skalabilitas dan kerapian (Blueprints pattern):

```text
/my_drama_app
├── /app
│   ├── __init__.py          # Setup Flask, DB, LoginManager
│   ├── models.py            # Definisi SQLAlchemy Class
│   ├── decorators.py        # Custom decorator (@admin_required)
│   ├── /static              # CSS, JS, Images
│   ├── /templates
│   │   ├── /admin           # Admin HTML templates
│   │   ├── /auth            # Login HTML templates
│   │   ├── /main            # Public HTML templates (Home, Watch)
│   │   └── base.html
│   ├── /blueprints
│   │   ├── admin.py         # Routes untuk dashboard admin
│   │   ├── auth.py          # Routes untuk Google Login
│   │   ├── main.py          # Routes untuk public viewing
│   │   └── payment.py       # Routes untuk handling transaksi
├── config.py                # Config (Database URI, Google Client ID, Secret Key)
├── run.py                   # Entry point
└── requirements.txt

```

---

## 6. Next Steps (Action Plan)

Berikut adalah tahapan pengerjaan yang disarankan:

1. **Phase 1: Setup & Auth:**
* Setup Flask project structure.
* Integrasi Database MySQL.
* Implementasi Google OAuth Login.
* Buat User Role logic.


2. **Phase 2: Content Management (Admin):**
* Buat Admin Dashboard.
* CRUD Movies & Episodes.
* Upload/Input URL video.


3. **Phase 3: Public Interface & Player:**
* Halaman Home (List Movies).
* Halaman Detail Movie (List Episodes).
* Halaman Watch (Player) dengan logika `is_free`.


4. **Phase 4: Subscription & Payment:**
* CRUD Subscription Plans di Admin.
* Halaman Pricing di User.
* Integrasi logika Trakteer (Manual confirm atau Webhook simulation).
* Logic penguncian video (Gembok).


5. **Phase 5: Favorites & Polishing:**
* Fitur Favorite.
* SEO Settings di Admin.
* Security Audit (CSRF, SQL Injection checks).
