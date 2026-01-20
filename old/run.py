import requests
from bs4 import BeautifulSoup
import re
import json
from time import sleep
import os
import sys
import platform
from datetime import datetime

# --- Konfigurasi Global ---
"""
Skrip ini digunakan untuk mengambil data film dan episode dari situs dracinlovers.com.
Fitur utama:
1. Melanjutkan scraping dari ID terakhir yang sudah didownload
2. Menyimpan data secara berkala untuk mencegah kehilangan data
3. Menampilkan progres dan estimasi waktu
4. Mendukung sistem operasi Windows dan Mac
5. Menangani error dan interupsi dengan menyimpan data backup

Cara penggunaan:
- Tanpa parameter: python run.py (melanjutkan dari ID terakhir)
- Dengan parameter: python run.py [start_id] [end_id]

Contoh: python run.py 3001 5000
"""

BASE_URL = 'https://www.dracinlovers.com/'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}
# Token dan PHPSESSID ini mungkin perlu diperbarui jika sesi kedaluwarsa
TOKEN = "f90cf33cadc3fcde48ed9aa36950e5ed97a44bdba5e6dd18df16c899040c7db1"
PHPSESSID = "pbk1kqd6loh9s5cfdeb3jo6j9l"

def get_file_size_mb(filename):
    """Mendapatkan ukuran file dalam MB."""
    try:
        if os.path.exists(filename):
            size_bytes = os.path.getsize(filename)
            return size_bytes / (1024 * 1024)  # Convert to MB
        return 0
    except Exception:
        return 0

def get_last_movie_id(filename):
    """Fungsi untuk mendapatkan movie_id terakhir dari file JSON yang sudah ada."""
    if not os.path.exists(filename):
        return 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data:
            return 0
            
        # Mencari movie_id terbesar dari data yang sudah ada
        max_id = 0
        for movie in data:
            try:
                movie_id = int(movie.get('movie_id', 0))
                if movie_id > max_id:
                    max_id = movie_id
            except (ValueError, TypeError):
                continue
                
        return max_id
    except Exception as e:
        print(f"[!] Error saat membaca file {filename}: {e}")
        return 0

def print_data_summary(data):
    """Menampilkan ringkasan data yang sudah didownload."""
    if not data:
        print("Tidak ada data yang tersedia.")
        return
    
    # Hitung total episode
    total_episodes = 0
    for movie in data:
        total_episodes += len(movie.get('episodes', []))
    
    # Cari movie_id terkecil dan terbesar
    min_id = float('inf')
    max_id = 0
    for movie in data:
        try:
            movie_id = int(movie.get('movie_id', 0))
            min_id = min(min_id, movie_id)
            max_id = max(max_id, movie_id)
        except (ValueError, TypeError):
            continue
    
    print(f"\n{'='*50}")
    print(f"RINGKASAN DATA:")
    print(f"- Total film: {len(data)}")
    print(f"- Total episode: {total_episodes}")
    print(f"- Range movie_id: {min_id} - {max_id}")
    print(f"{'='*50}\n")

def scrape_all_data(start_id=1, end_id=10000, existing_data=None):
    """Fungsi utama untuk mengambil semua data film dan episodenya langsung dari halaman detail."""
    all_movies_data = existing_data if existing_data else []
    # Scraping dari start_id hingga end_id
    total_ids = end_id - start_id + 1
    processed = 0
    success_count = 0
    start_time = datetime.now()
    
    for movie_id in range(start_id, end_id + 1):
        # Langsung menargetkan halaman detail karena semua info ada di sana
        url = f"{BASE_URL}detail2.php?id={movie_id}&token={TOKEN}"
        print(f"[*] Memproses movie_id: {movie_id} -> {url}")

        try:
            headers = HEADERS.copy()
            headers['Cookie'] = f"PHPSESSID={PHPSESSID}; filemanager=h5e165onl8npsmph4340464m1q"
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() # Cek jika ada error HTTP (spt 404, 500)

            # Jika halaman mengembalikan pesan akses ditolak, lewati
            if "Akses Bermasalah" in response.text or "Sesi tidak valid" in response.text:
                print(f"  └─ [!] Sesi tidak valid atau akses ditolak untuk movie_id: {movie_id}. Mungkin token/PHPSESSID perlu diperbarui.")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. Ambil Judul Serial dari <h1 class="movie-title">
            series_title_tag = soup.find('h1', class_='movie-title')
            series_title = series_title_tag.get_text(strip=True) if series_title_tag else None

            # 2. Ambil Poster dan Deskripsi
            poster_div = soup.find('div', class_='play-overlay')
            poster_url = None
            if poster_div and poster_div.get('style'):
                style_attr = poster_div.get('style')
                match = re.search(r"url\('([^']+)'\)", style_attr)
                if match:
                    poster_url = match.group(1)

            desc_tag = soup.find('p', class_='movie-description')
            movie_description = desc_tag.get_text(strip=True) if desc_tag else None

            # 3. Ekstrak Data Episode dari <script>
            script_tags = soup.find_all("script")
            episodes_data_str = None
            for tag in script_tags:
                if "const episodesData =" in tag.text:
                    match = re.search(r'const episodesData = (\s*.*?\s*);', tag.text, re.DOTALL)
                    if match:
                        episodes_data_str = match.group(1)
                        break
            
            episodes_list = []
            if episodes_data_str:
                try:
                    episodes_json = json.loads(episodes_data_str)
                    for ep in episodes_json:
                        episodes_list.append({
                            "movie_id": ep.get("movie_id"),
                            "episode_title": ep.get("title"),
                            "episode_id": ep.get("episode_id"),
                            "episode_number": ep.get("episode_number"),
                            "content_url": ep.get("content_url"),
                            "is_free": ep.get("is_free")
                        })
                except json.JSONDecodeError:
                    print(f"    └─ [!] Gagal mem-parsing JSON episode untuk movie_id: {movie_id}")

            # Validasi: Pastikan judul serial ditemukan sebelum menyimpan
            if series_title:
                movie_data = {
                    'movie_id': str(movie_id),
                    'series_title': series_title,
                    'poster_url': poster_url,
                    'movie_description': movie_description,
                    'episodes': episodes_list
                }
                all_movies_data.append(movie_data)
                success_count += 1
                print(f"  └─ [✓] Berhasil diproses: {series_title} ({len(episodes_list)} episode)")
            else:
                print(f"  └─ [x] Gagal mendapatkan judul serial, melewati movie_id: {movie_id}")

            # Menampilkan progres
            processed += 1
            elapsed_time = (datetime.now() - start_time).total_seconds()
            progress = (processed / total_ids) * 100
            est_remaining = (elapsed_time / processed) * (total_ids - processed) if processed > 0 else 0
            est_remaining_min = int(est_remaining // 60)
            est_remaining_sec = int(est_remaining % 60)
            
            print(f"  └─ Progres: {progress:.1f}% ({processed}/{total_ids}) | Berhasil: {success_count} | Estimasi sisa waktu: {est_remaining_min} menit {est_remaining_sec} detik")
            
            # Simpan data secara berkala (setiap 10 film berhasil diproses)
            if success_count > 0 and success_count % 10 == 0:
                temp_filename = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    f"dracinlovers_temp.json"
                )
                try:
                    with open(temp_filename, 'w', encoding='utf-8') as f:
                        json.dump(all_movies_data, f, indent=4, ensure_ascii=False)
                    print(f"  └─ [💾] Data sementara disimpan ke {temp_filename}")
                except Exception as e:
                    print(f"  └─ [!] Gagal menyimpan data sementara: {e}")
            
            sleep(0.5)  # Jeda agar tidak membebani server

        except requests.exceptions.RequestException as e:
            print(f"  └─ [!] Error request untuk movie_id {movie_id}: {e}")
            continue
        except Exception as e:
            print(f"  └─ [!] Terjadi error tak terduga untuk movie_id {movie_id}: {e}")
            continue
            
    return all_movies_data

if __name__ == "__main__":
    # Deteksi sistem operasi
    system_name = platform.system()
    print(f"Sistem operasi terdeteksi: {system_name}")
    
    # Pastikan path file kompatibel dengan Windows dan Mac
    output_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dracinlovers_all_data_final.json')
    
    # Mendapatkan movie_id terakhir yang sudah didownload
    last_movie_id = get_last_movie_id(output_filename)
    start_id = last_movie_id + 1
    
    # Cek parameter command line untuk start_id dan end_id
    if len(sys.argv) > 1:
        try:
            start_id = int(sys.argv[1])
            print(f"Menggunakan start_id dari parameter: {start_id}")
        except ValueError:
            print(f"Parameter start_id tidak valid, menggunakan nilai default: {start_id}")
    
    end_id = 10000  # Batas atas ID yang akan di-scrape
    if len(sys.argv) > 2:
        try:
            end_id = int(sys.argv[2])
            print(f"Menggunakan end_id dari parameter: {end_id}")
        except ValueError:
            print(f"Parameter end_id tidak valid, menggunakan nilai default: {end_id}")
    
    print(f"\n{'='*50}")
    print(f"Memulai proses scraping dari movie_id {start_id} hingga {end_id}...")
    print(f"Waktu mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    # Membaca data yang sudah ada jika file ada
    existing_data = []
    if os.path.exists(output_filename):
        try:
            # Cek ukuran file, jika terlalu besar, buat file baru
            file_size_mb = get_file_size_mb(output_filename)
            if file_size_mb > 50:  # Jika file lebih dari 50MB
                print(f"[!] File {output_filename} terlalu besar ({file_size_mb:.1f} MB).")
                print("Membuat file baru untuk data yang akan di-scrape...")
                # Buat nama file baru dengan range ID
                output_filename = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    f"dracinlovers_data_{start_id}_to_{end_id}.json"
                )
                print(f"Data baru akan disimpan ke: {output_filename}")
            else:
                # Baca data yang sudah ada
                with open(output_filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                print(f"Berhasil memuat {len(existing_data)} data film yang sudah ada.")
                # Tampilkan ringkasan data yang sudah ada
                print_data_summary(existing_data)
        except Exception as e:
            print(f"[!] Error saat membaca file {output_filename}: {e}")
            print("Melanjutkan dengan data kosong...")
    
    # Melakukan scraping data baru
    try:
        final_data = scrape_all_data(start_id, end_id, existing_data)
        
        # Menyimpan hasil scraping ke file
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=4, ensure_ascii=False)
            
            print(f"\n{'='*50}")
            print(f"✅ Selesai. Total serial yang berhasil di-scrape: {len(final_data)}")
            print(f"Data lengkap tersimpan di file: {output_filename}")
            print(f"Ukuran file: {get_file_size_mb(output_filename):.2f} MB")
            print(f"Waktu selesai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")
            
            # Tampilkan ringkasan data
            print_data_summary(final_data)
        except Exception as save_error:
            print(f"\n[!] Error saat menyimpan file utama: {save_error}")
            # Coba simpan ke file backup jika gagal menyimpan ke file utama
            backup_filename = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"dracinlovers_save_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(backup_filename, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=4, ensure_ascii=False)
            print(f"[💾] Data disimpan ke file backup: {backup_filename}")
    except KeyboardInterrupt:
        print("\n\n[!] Proses scraping dihentikan oleh pengguna.")
        # Simpan data yang sudah berhasil di-scrape
        backup_filename = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"dracinlovers_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"[💾] Data yang sudah di-scrape disimpan ke {backup_filename}")
    except Exception as e:
        print(f"\n\n[!] Terjadi error: {e}")
        # Simpan data yang sudah berhasil di-scrape
        backup_filename = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"dracinlovers_error_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"[💾] Data yang sudah di-scrape disimpan ke {backup_filename}")