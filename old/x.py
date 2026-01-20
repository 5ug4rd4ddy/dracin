#!/usr/bin/env python3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import re
import json
from time import sleep
import os
import sys
import platform
from datetime import datetime
from urllib.parse import urljoin
import argparse
import logging
import tempfile

# ----------------------------
# Konfigurasi (ubah jika perlu)
# ----------------------------
BASE_URL = 'https://www.dracinlovers.com/'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
}
# NOTE: lebih aman meletakkan TOKEN & PHPSESSID di env var atau file config
TOKEN = "39e5201fb393fcb60d8a3f285be13161909fdf905760e2ab6e340c3817b38584"
PHPSESSID = "a8cpo969ko3ev6hat1f8nh07jl"

# Simpan sementara tiap N film sukses
TEMP_SAVE_INTERVAL = 10
# Delay antar request (jangan terlalu kecil)
REQUEST_DELAY = 0.5
# Maks ukuran file output sebelum membuat file baru (MB)
MAX_OUTPUT_MB = 50

# Berapa episode pertama yang dipaksa is_free = 1
FREE_EPISODES_COUNT = 10

# Logging sederhana
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ----------------------------
# Utility functions
# ----------------------------
def get_file_size_mb(filename):
    try:
        if os.path.exists(filename):
            size_bytes = os.path.getsize(filename)
            return size_bytes / (1024 * 1024)
        return 0
    except Exception:
        return 0

def get_last_movie_id(filename):
    """Ambil movie_id terbesar dari file JSON jika ada."""
    if not os.path.exists(filename):
        return 0
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return 0
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
        logging.warning(f"Error membaca file {filename}: {e}")
        return 0

def print_data_summary(data):
    if not data:
        logging.info("Tidak ada data yang tersedia.")
        return
    total_episodes = sum(len(m.get('episodes', [])) for m in data)
    ids = []
    for m in data:
        try:
            ids.append(int(m.get('movie_id', 0)))
        except Exception:
            continue
    min_id = min(ids) if ids else 0
    max_id = max(ids) if ids else 0
    logging.info("="*40)
    logging.info("RINGKASAN DATA:")
    logging.info(f"- Total film: {len(data)}")
    logging.info(f"- Total episode: {total_episodes}")
    logging.info(f"- Range movie_id: {min_id} - {max_id}")
    logging.info("="*40)

def atomic_write_json(path, data):
    """Tulis JSON ke file secara atomik (menulis ke tmp lalu rename)."""
    dirn = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dirn, prefix='.tmp_', suffix='.json')
    try:
        os.close(fd)
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise

# ----------------------------
# HTTP session + retry
# ----------------------------
def create_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429,500,502,503,504])
    s.mount('https://', HTTPAdapter(max_retries=retries))
    s.mount('http://', HTTPAdapter(max_retries=retries))
    return s

# ----------------------------
# Parsing helper
# ----------------------------
def extract_episodes_from_scripts(soup):
    """Cari JS var episodesData dan parse JSON array-nya secara robust."""
    script_tags = soup.find_all("script")
    episodes_list = []
    for tag in script_tags:
        text = tag.string or tag.text or ""
        if "const episodesData" in text:
            try:
                idx = text.find("const episodesData")
                start_idx = text.find('[', idx)
                if start_idx == -1:
                    continue
                end_marker = text.find('];', start_idx)
                if end_marker == -1:
                    end_marker = text.find(']', start_idx)
                    if end_marker == -1:
                        continue
                json_str = text[start_idx:end_marker+1].strip()
                episodes_json = json.loads(json_str)
                if isinstance(episodes_json, list):
                    for ep in episodes_json:
                        episodes_list.append({
                            "movie_id": ep.get("movie_id"),
                            "episode_title": ep.get("title"),
                            "episode_id": ep.get("episode_id"),
                            "episode_number": ep.get("episode_number"),
                            "content_url": ep.get("content_url"),
                            "is_free": ep.get("is_free")
                        })
                break
            except json.JSONDecodeError:
                logging.debug("Gagal json.loads episodesData, melewati tag ini.")
                continue
            except Exception as e:
                logging.debug(f"Error saat ekstrak episodesData: {e}")
                continue
    return episodes_list

def extract_poster_from_scripts(soup):
    """
    Cari URL poster di dalam tag <script>.
    Menangani pola:
      poster: 'https://...jpg'
      poster: "https://...jpg"
      poster: episode.poster_url || 'https://...jpg'
      poster: episode.poster_url || "https://...jpg"
    Mengembalikan URL pertama yang valid, atau None.
    """
    script_tags = soup.find_all("script")
    poster_regex = re.compile(
        r"poster\s*:\s*(?:episode\.poster_url\s*\|\|\s*)?['\"]([^'\"]+)['\"]",
        re.IGNORECASE
    )

    for tag in script_tags:
        text = tag.string or tag.text or ""
        if "poster" not in text:
            continue
        m = poster_regex.search(text)
        if m:
            poster_url = m.group(1).strip()
            try:
                poster_url = urljoin(BASE_URL, poster_url)
            except Exception:
                pass
            return poster_url
    return None

# ----------------------------
# Main scraping function
# ----------------------------
def scrape_all_data(session, start_id=1, end_id=10000, existing_data=None, output_temp_path=None):
    all_movies_data = existing_data[:] if existing_data else []
    total_ids = end_id - start_id + 1
    processed = 0
    success_count = 0
    start_time = datetime.now()

    for movie_id in range(start_id, end_id + 1):
        url = f"{BASE_URL}detail2.php?id={movie_id}&token={TOKEN}"
        logging.info(f"Memproses movie_id: {movie_id} -> {url}")
        try:
            headers = HEADERS.copy()
            headers['Cookie'] = f"PHPSESSID={PHPSESSID}; filemanager=h5e165onl8npsmph4340464m1q"
            resp = session.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            if "Akses Bermasalah" in resp.text or "Sesi tidak valid" in resp.text:
                logging.warning(f"Sesi tidak valid atau akses ditolak untuk movie_id: {movie_id}. Lanjutkan.")
                processed += 1
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = (processed / total_ids) * 100
                logging.info(f"Progress: {progress:.1f}% ({processed}/{total_ids}) | Sukses: {success_count}")
                sleep(REQUEST_DELAY)
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Judul
            series_title_tag = soup.find('h1', class_='movie-title')
            series_title = series_title_tag.get_text(strip=True) if series_title_tag else None

            # Poster dari style background-image (prioritas pertama)
            poster_url = None
            poster_div = soup.find('div', class_='play-overlay')
            if poster_div and poster_div.get('style'):
                style_attr = poster_div.get('style')
                m = re.search(r"url\(['\"]?([^'\"\)]+)['\"]?\)", style_attr)
                if m:
                    poster_url = m.group(1)
                    poster_url = urljoin(BASE_URL, poster_url)

            # Jika masih kosong, coba ekstrak dari script JS (newSource.poster)
            if not poster_url:
                poster_from_js = extract_poster_from_scripts(soup)
                if poster_from_js:
                    poster_url = poster_from_js

            # Description
            desc_tag = soup.find('p', class_='movie-description')
            movie_description = desc_tag.get_text(strip=True) if desc_tag else None

            # Episodes
            episodes_list = extract_episodes_from_scripts(soup)

            # Override: 10 episode pertama menjadi gratis (is_free = 1)
            for ep in episodes_list:
                try:
                    num = int(ep.get("episode_number", 0))
                    if 1 <= num <= FREE_EPISODES_COUNT:
                        ep["is_free"] = 1
                    else:
                        # pastikan non-first-10 tetap mengikuti sumber asli (atau default 0)
                        ep["is_free"] = ep.get("is_free", 0)
                except Exception:
                    # jika episode_number tidak bisa di-parse, jangan crash — set default
                    ep["is_free"] = ep.get("is_free", 0)

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
                logging.info(f"  [✓] {series_title} ({len(episodes_list)} episode)")
            else:
                logging.info(f"  [x] Gagal mendapatkan judul. Melewati movie_id: {movie_id}")

            # progres & estimasi
            processed += 1
            elapsed_time = (datetime.now() - start_time).total_seconds()
            progress = (processed / total_ids) * 100
            est_remaining = (elapsed_time / processed) * (total_ids - processed) if processed > 0 else 0
            est_min = int(est_remaining // 60)
            est_sec = int(est_remaining % 60)
            logging.info(f"  Progres: {progress:.1f}% ({processed}/{total_ids}) | Berhasil: {success_count} | Est. sisa: {est_min}m {est_sec}s")

            # Simpan sementara setiap TEMP_SAVE_INTERVAL sukses
            if success_count > 0 and success_count % TEMP_SAVE_INTERVAL == 0 and output_temp_path:
                try:
                    atomic_write_json(output_temp_path, all_movies_data)
                    logging.info(f"  [💾] Data sementara disimpan ke {output_temp_path}")
                except Exception as e:
                    logging.warning(f"  [!] Gagal menyimpan data sementara: {e}")

            sleep(REQUEST_DELAY)

        except requests.exceptions.RequestException as e:
            logging.warning(f"  [!] Request error untuk movie_id {movie_id}: {e}")
            processed += 1
            sleep(REQUEST_DELAY)
            continue
        except Exception as e:
            logging.warning(f"  [!] Error tak terduga untuk movie_id {movie_id}: {e}")
            processed += 1
            sleep(REQUEST_DELAY)
            continue

    return all_movies_data

# ----------------------------
# CLI & main
# ----------------------------
def main():
    system_name = platform.system()
    logging.info(f"Sistem operasi terdeteksi: {system_name}")

    parser = argparse.ArgumentParser(description="Scrape dracinlovers detail pages (with resume & temp save).")
    parser.add_argument('start_id', nargs='?', type=int, help='Start ID (optional)')
    parser.add_argument('end_id', nargs='?', type=int, default=10000, help='End ID (optional, default=10000)')
    parser.add_argument('--out', '-o', help='Output filename (optional)')
    args = parser.parse_args()

    # default output
    default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dracinlovers_all_data_final.json')
    output_filename = args.out if args.out else default_output

    # determining start_id: if arg given use it, else use last_movie_id+1
    last_movie_id = get_last_movie_id(output_filename)
    inferred_start = last_movie_id + 1 if last_movie_id >= 1 else 1
    start_id = inferred_start
    if args.start_id:
        start_id = args.start_id
        logging.info(f"Menggunakan start_id dari parameter: {start_id}")
    end_id = args.end_id
    logging.info(f"Memulai scraping dari movie_id {start_id} hingga {end_id}...")

    # load existing data jika file ada & ukurannya wajar
    existing_data = []
    if os.path.exists(output_filename):
        try:
            size_mb = get_file_size_mb(output_filename)
            if size_mb > MAX_OUTPUT_MB:
                output_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"dracinlovers_data_{start_id}_to_{end_id}.json")
                logging.info(f"File lama terlalu besar ({size_mb:.1f} MB). Data baru akan disimpan ke: {output_filename}")
            else:
                with open(output_filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                logging.info(f"Berhasil memuat {len(existing_data)} data film yang sudah ada.")
                print_data_summary(existing_data)
        except Exception as e:
            logging.warning(f"Error saat membaca file {output_filename}: {e}")
            existing_data = []

    session = create_session()
    temp_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dracinlovers_temp.json")

    final_data = None
    try:
        final_data = scrape_all_data(session, start_id, end_id, existing_data, output_temp_path=temp_filename)
        # Simpan final data secara atomik
        atomic_write_json(output_filename, final_data)
        logging.info("\n" + "="*40)
        logging.info(f"✅ Selesai. Total serial yang berhasil di-scrape: {len(final_data)}")
        logging.info(f"Data lengkap tersimpan di file: {output_filename}")
        logging.info(f"Ukuran file: {get_file_size_mb(output_filename):.2f} MB")
        logging.info(f"Waktu selesai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("="*40)
        print_data_summary(final_data)
    except KeyboardInterrupt:
        logging.warning("\n[!] Proses dihentikan oleh pengguna (KeyboardInterrupt). Menyimpan progres...")
        backup_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       f"dracinlovers_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            data_to_save = final_data if final_data is not None else existing_data
            atomic_write_json(backup_filename, data_to_save)
            logging.info(f"[💾] Data yang sudah di-scrape disimpan ke {backup_filename}")
        except Exception as e:
            logging.error(f"[!] Gagal menyimpan backup: {e}")
    except Exception as e:
        logging.error(f"\n[!] Terjadi error: {e}")
        backup_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       f"dracinlovers_error_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            data_to_save = final_data if final_data is not None else existing_data
            atomic_write_json(backup_filename, data_to_save)
            logging.info(f"[💾] Data yang sudah di-scrape disimpan ke {backup_filename}")
        except Exception as e2:
            logging.error(f"[!] Gagal menyimpan error-backup: {e2}")

if __name__ == "__main__":
    main()
