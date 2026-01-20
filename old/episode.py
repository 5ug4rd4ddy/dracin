import requests
from bs4 import BeautifulSoup
import re
import json

# --- Konfigurasi ---
MOVIE_ID = 2
TOKEN = "2236fb650af281e6bf25a38735ae9df36ef0763fa0bf2b0ab50dc1890d8ac1af"
PHPSESSID = "ulp325n6avnamfh4u927dn4rus"
URL = f"https://www.dracinlovers.com/detail.php?id={MOVIE_ID}&token={TOKEN}"

headers = {
    "Host": "www.dracinlovers.com",
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
    "Cookie": f"PHPSESSID={PHPSESSID}; filemanager=h5e165onl8npsmph4340464m1q",
}

# --- Proses Request ---
response = requests.get(URL, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# --- Ekstrak Data dari <script> ---
script_tags = soup.find_all("script")
episodes_data = None

for tag in script_tags:
    if "const episodesData =" in tag.text:
        match = re.search(r'const episodesData = (\[.*?\]);', tag.text, re.DOTALL)
        if match:
            episodes_data = json.loads(match.group(1))
            break

# --- Validasi ---
if not episodes_data:
    print("Gagal menemukan episodesData.")
    exit()

# --- Format Output ---
output_data = []
for ep in episodes_data:
    output_data.append({
        "movie_id": ep.get("movie_id"),
        "title": ep.get("title"),
        "episode_id": ep.get("episode_id"),
        "episode_number": ep.get("episode_number"),
        "content_url": ep.get("content_url"),
    })

# --- Simpan ke File JSON ---
filename = f"dracin_episode_{MOVIE_ID}.json"
with open(filename, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4)

print(f"✅ Data berhasil disimpan ke {filename}")
