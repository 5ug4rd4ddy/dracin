import requests
from bs4 import BeautifulSoup
import json
from time import sleep

# ==== INPUT RANGE ====
start_id = int(input("Masukkan START ID: "))
end_id   = int(input("Masukkan END ID: "))

# Validasi
if end_id < start_id:
    raise ValueError("END ID harus lebih besar dari START ID!")

# =====================

base_url = 'https://www.dracinlovers.com/index.php?id='
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

movies = []

for movie_id in range(start_id, end_id + 1):
    url = f"{base_url}{movie_id}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        container = soup.find('div', class_='container')
        if not container:
            print(f"[x] ID {movie_id} - Container not found")
            continue

        # Poster
        poster_div = container.find('div', class_='poster')
        poster_img = poster_div.find('img') if poster_div else None
        poster_url = poster_img.get('src') if poster_img else None

        # Title & Description
        content_div = container.find('div', class_='content')
        title_tag = content_div.find('h1') if content_div else None
        desc_tag = content_div.find('p', class_='description') if content_div else None

        movie_title = title_tag.get_text(strip=True) if title_tag else None
        movie_description = desc_tag.get_text(strip=True) if desc_tag else None

        if movie_title and poster_url and movie_description:
            movies.append({
                'movie_id': str(movie_id),
                'movie_title': movie_title,
                'poster_url': poster_url,
                'movie_description': movie_description
            })
            print(f"[✓] ID {movie_id} - {movie_title}")
        else:
            print(f"[x] ID {movie_id} - Incomplete info, skipped")

        sleep(0.2)

    except Exception as e:
        print(f"[!] Error processing ID {movie_id}: {e}")
        continue

# Save to JSON
filename = f"movies_{start_id}_{end_id}.json"
with open(filename, 'w', encoding='utf-8') as f:
    json.dump(movies, f, indent=4, ensure_ascii=False)

print(f"\n✅ Done. Total movies scraped: {len(movies)}")
print(f"📁 File saved as: {filename}")
