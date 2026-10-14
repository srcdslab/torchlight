import asyncio
import io
import ipaddress
import json
import logging
import socket
from collections.abc import Callable
from typing import Any

import aiohttp
import magic
import yt_dlp
from aiohttp.abc import ResolveResult
from bs4 import BeautifulSoup
from PIL import Image
from yarl import URL

from torchlight.Utils import Utils

logger = logging.getLogger(__name__)


ALLOWED_URL_SCHEMES = ("http", "https")
MAX_REDIRECTS = 5
REDIRECT_STATUSES = (301, 302, 303, 307, 308)


class NonPublicURLError(Exception):
    """Raised when a URL uses a forbidden scheme or points to a non-public address."""


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


def _looks_like_ip_literal(host: str) -> bool:
    # Same heuristic aiohttp uses to skip DNS resolution for a host, so every host
    # it would connect to directly gets checked here instead of by the resolver.
    return ":" in host or host.replace(".", "").isdigit()


def _check_url(url: URL) -> str:
    """Validate scheme and literal-IP host of a URL, return its host for resolution."""
    if url.scheme not in ALLOWED_URL_SCHEMES:
        raise NonPublicURLError("Only http:// and https:// URLs are allowed")

    host = url.raw_host
    if not host:
        raise NonPublicURLError("URL has no host")

    if _looks_like_ip_literal(host) and not _is_public_ip(host):
        raise NonPublicURLError("URL points to a non-public address")

    return host


class PublicOnlyResolver(aiohttp.ThreadedResolver):
    """Resolver that drops every non-public address, so connections (including
    redirect hops) can only reach the public internet. Resolving at connect time
    also covers DNS rebinding between a pre-check and the actual request."""

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        results = await super().resolve(host, port, family)
        public = [result for result in results if _is_public_ip(result["host"])]
        if not public:
            raise NonPublicURLError("URL points to a non-public address")
        return public


async def assert_public_url(url: str) -> None:
    """Raise NonPublicURLError unless url is http(s) and its host only resolves to public addresses."""
    try:
        parsed = URL(url)
    except ValueError as exc:
        raise NonPublicURLError("Invalid URL") from exc

    host = _check_url(parsed)
    if _looks_like_ip_literal(host):
        return

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise NonPublicURLError(f"Could not resolve host '{host}'") from exc

    addresses = {str(info[4][0]) for info in infos}
    if not addresses or not all(_is_public_ip(address) for address in addresses):
        raise NonPublicURLError("URL points to a non-public address")


def _parse_content_length(raw: str) -> int:
    try:
        length = int(raw)
    except ValueError:
        return -1
    return length if length >= 0 else -1


# @profile
async def get_url_data(url: str) -> tuple[bytes, str, int]:
    current_url = URL(url)
    connector = aiohttp.TCPConnector(resolver=PublicOnlyResolver())
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as session:
        # Redirects are followed by hand so each hop's scheme and literal-IP host
        # are checked; hostnames are filtered by PublicOnlyResolver on connect.
        for _ in range(MAX_REDIRECTS + 1):
            _check_url(current_url)
            async with session.get(current_url, allow_redirects=False) as resp:
                location = resp.headers.get("Location")
                if resp.status in REDIRECT_STATUSES and location:
                    current_url = resp.url.join(URL(location))
                    continue

                content_type: str = resp.headers.get("Content-Type", "")
                content_length = _parse_content_length(resp.headers.get("Content-Length", ""))
                content = await resp.content.read(65536)
                return content, content_type, content_length

    raise Exception(f"Too many redirects (max {MAX_REDIRECTS})")


def get_page_metadata(*, content: bytes, content_type: str, content_length: int) -> str:
    metadata = ""

    if content_type and content_type.startswith("text"):
        if not content_type.startswith("text/plain"):
            Soup = BeautifulSoup(content.decode("utf-8", errors="ignore"), "lxml")
            if Soup.title:
                metadata = f"[URL] {Soup.title.string}"
    elif content_type and content_type.startswith("image"):
        with io.BytesIO(content) as fp, Image.open(fp) as im:
            metadata = (
                f"[IMAGE] {im.format} | Width: {im.size[0]} | Height: {im.size[1]}"
                f" | Size: {Utils.HumanSize(content_length)}"
            )
    else:
        Filetype = magic.from_buffer(bytes(content))
        metadata = f"[FILE] {Filetype} | Size: {Utils.HumanSize(content_length)}"
    return metadata


def get_page_text(*, content: bytes, content_type: str, content_length: int) -> str:
    text = ""

    if content_type and content_type.startswith("text"):
        if content_type.startswith("text/plain"):
            text = content.decode("utf-8", errors="ignore")
    return text


async def print_url_metadata(url: str, callback: Callable) -> None:
    content, content_type, content_length = await get_url_data(url=url)

    metadata = get_page_metadata(
        content=content,
        content_type=content_type,
        content_length=content_length,
    )

    if len(metadata) > 0:
        callback(metadata)


# @profile
async def get_url_text(url: str) -> str:
    content, content_type, content_length = await get_url_data(url=url)
    return get_page_text(
        content=content,
        content_type=content_type,
        content_length=content_length,
    )


def get_url_real_time(url: str) -> int:
    temp_pos: int = -1

    if (
        (temp_pos := url.find("&t=")) != -1
        or (temp_pos := url.find("?t=")) != -1
        or (temp_pos := url.find("#t=")) != -1
    ):
        time_str = url[temp_pos + 3 :].split("&")[0].split("?")[0].split("#")[0]
        if time_str:
            return Utils.ParseTime(time_str)
    return 0


# @profile
def get_url_youtube_info(url: str, proxy: str = "", cookies: str = "") -> dict:
    # https://github.com/ytdl-org/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312
    # https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L192
    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "debug_printtraffic": False,
        "quiet": True,
        "no_warnings": True,
        "format": "m4a/bestaudio/best",
        "simulate": True,
        "keepvideo": False,
    }

    if proxy:
        ydl_opts["proxy"] = proxy

    if cookies:
        ydl_opts["cookiefile"] = cookies

    # Context-managed so YoutubeDL.close() runs: without it every !yt / !yts call
    # (and each retry in get_first_valid_entry) leaks the extractor's HTTP connection
    # pools and cookie jar until GC, which adds up on a long-running bot (issue #55).
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.add_default_info_extractors()
        return ydl.extract_info(url, download=False)


# @profile
def get_first_valid_entry(entries: list[Any], proxy: str = "", cookies: str = "") -> dict[str, Any]:
    for entry in entries:
        input_url = f"https://youtube.com/watch?v={entry['id']}"
        try:
            info = get_url_youtube_info(url=input_url, proxy=proxy, cookies=cookies)
            return info
        except yt_dlp.utils.DownloadError:
            logger.warning(f"Error trying to download <{input_url}>")
            pass
    raise Exception("No compatible youtube video found, try something else")


def get_audio_format(info: dict[str, Any]) -> str:
    for format in info["formats"]:
        if "audio_channels" in format:
            logger.debug(json.dumps(format, indent=2))
            return format["url"]
    raise Exception("No compatible audio format found, try something else")
