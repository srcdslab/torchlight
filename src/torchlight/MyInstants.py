import re
import secrets

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests

MYINSTANTS_URL = "https://www.myinstants.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def myinstants_get_random_sound(query: str | None) -> str | None:
    if not query:
        search_url = f"{MYINSTANTS_URL}/en/index/us/"
    else:
        search_url = f"{MYINSTANTS_URL}/en/search/?name={query}"

    r = requests.get(search_url, headers=HEADERS, timeout=10)

    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    buttons = soup.find_all("button", onclick=True)
    mp3_paths = []

    for btn in buttons:
        onclick_value = btn["onclick"]
        if "play(" in onclick_value:
            match = re.search(r"play\('(.+?\.mp3)'", onclick_value)
            if match:
                mp3_paths.append(match.group(1))

    if not mp3_paths:
        return None

    mp3_url = urljoin(MYINSTANTS_URL, secrets.choice(mp3_paths))
    return mp3_url
