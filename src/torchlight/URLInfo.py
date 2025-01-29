import asyncio
import io
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp
import magic
import yt_dlp
from bs4 import BeautifulSoup
from PIL import Image

from torchlight.Utils import Utils

logger = logging.getLogger(__name__)


# @profile
async def get_url_data(url: str) -> tuple[bytes, str, int]:
    async with aiohttp.ClientSession() as session:
        resp = await asyncio.wait_for(session.get(url), 5)
        if resp:
            content_type: str = resp.headers.get("Content-Type", "")
            content_length_raw: str = resp.headers.get("Content-Length", "")
            content = await asyncio.wait_for(resp.content.read(65536), 5)

            content_length = -1
            if content_length_raw:
                content_length = int(content_length_raw)

            resp.close()
    return content, content_type, content_length


def get_page_metadata(*, content: bytes, content_type: str, content_length: int) -> str:
    metadata = ""

    if content_type and content_type.startswith("text"):
        if not content_type.startswith("text/plain"):
            Soup = BeautifulSoup(content.decode("utf-8", errors="ignore"), "lxml")
            if Soup.title:
                metadata = f"[URL] {Soup.title.string}"
    elif content_type and content_type.startswith("image"):
        fp = io.BytesIO(content)
        im = Image.open(fp)
        metadata = (
            f"[IMAGE] {im.format} | Width: {im.size[0]} | Height: {im.size[1]}"
            f" | Size: {Utils.HumanSize(content_length)}"
        )
        fp.close()
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
def get_url_youtube_info(url: str, proxy: str = "") -> dict:
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
    ydl = yt_dlp.YoutubeDL(ydl_opts)
    ydl.add_default_info_extractors()
    return ydl.extract_info(url, download=False)


# @profile
def get_first_valid_entry(entries: list[Any], proxy: str = "") -> dict[str, Any]:
    for entry in entries:
        input_url = f"https://youtube.com/watch?v={entry['id']}"
        try:
            info = get_url_youtube_info(url=input_url, proxy=proxy)
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
