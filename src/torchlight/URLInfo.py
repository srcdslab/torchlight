import asyncio
import io
from collections.abc import Callable

import aiohttp
import magic
import youtube_dl
from bs4 import BeautifulSoup
from PIL import Image

from torchlight.Utils import Utils


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


def get_page_metadata(
    *, content: bytes, content_type: str, content_length: int
) -> str:
    metadata = ""

    if content_type and content_type.startswith("text"):
        if not content_type.startswith("text/plain"):
            Soup = BeautifulSoup(
                content.decode("utf-8", errors="ignore"), "lxml"
            )
            if Soup.title:
                metadata = f"[URL] {Soup.title.string}"
    elif content_type and content_type.startswith("image"):
        fp = io.BytesIO(content)
        im = Image.open(fp)
        metadata = "[IMAGE] {} | Width: {} | Height: {} | Size: {}".format(
            im.format,
            im.size[0],
            im.size[1],
            Utils.HumanSize(content_length),
        )
        fp.close()
    else:
        Filetype = magic.from_buffer(bytes(content))
        metadata = "[FILE] {} | Size: {}".format(
            Filetype, Utils.HumanSize(content_length)
        )
    return metadata


def get_page_text(
    *, content: bytes, content_type: str, content_length: int
) -> str:
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


def get_url_youtube_info(url: str) -> dict:
    # https://github.com/ytdl-org/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "format": "bestaudio/best",
    }
    ydl = youtube_dl.YoutubeDL(ydl_opts)
    ydl.add_default_info_extractors()
    return ydl.extract_info(url, download=False)
