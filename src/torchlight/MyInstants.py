import re
import secrets
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

MYINSTANTS_URL = "https://www.myinstants.com"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def myinstants_get_random_sound(
        query: str | None,
        proxy: str | None,
        search_only: bool = False,
    ) -> dict[str, str] | str | None:
    if not query:
        search_url = f"{MYINSTANTS_URL}/en/index/us/"
    else:
        search_url = f"{MYINSTANTS_URL}/en/search/"

    proxies = None
    if proxy:
        proxies = {
            "http": proxy,
            "https": proxy,
        }

    try:
        r = requests.get(
            search_url, headers=HEADERS, params={"name": query} if query else None, timeout=10, proxies=proxies
        )
    except requests.RequestException:
        return None

    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    buttons = soup.find_all("button", onclick=True)
    if search_only:
        mp3_paths: dict[str, str] = {}
    else:
        mp3_paths: list[str] = []

    for btn in buttons:
        onclick_value = btn["onclick"]
        if "play(" in onclick_value:
            match = re.search(r"play\('(.+?\.mp3)'", onclick_value)
            if match:
                if isinstance(mp3_paths, list):
                    mp3_paths.append(match.group(1))
                elif isinstance(mp3_paths, dict):
                    name = btn["title"]
                    name = name.removeprefix("Play ")
                    name = name.removesuffix(" sound")
                    # for secuirty purpose...
                    if len(name) > 20:
                        continue

                    mp3_paths[name] = name

    if not mp3_paths:
        return None

    if isinstance(mp3_paths, list):
        mp3_urls: str = urljoin(MYINSTANTS_URL, secrets.choice(mp3_paths))
    elif isinstance(mp3_paths, dict):
        mp3_urls: dict[str, str] = mp3_paths

    return mp3_urls
