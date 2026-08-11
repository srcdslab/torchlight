import asyncio
import datetime
import logging
import os
import socket
import struct
import time
import traceback
from asyncio import StreamReader, StreamWriter, Task
from asyncio.subprocess import Process
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import aiohttp

from torchlight.Torchlight import Torchlight

SAMPLEBYTES = 2


class FFmpegAudioPlayer:
    VALID_CALLBACKS = ["Play", "Stop", "Update"]

    def __init__(self, torchlight: Torchlight) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.config = self.torchlight.config["VoiceServer"]
        self.playing = False
        self.uri = ""
        self.position: int = 0

        self.host = self.config["Host"]
        self.port = self.config["Port"]
        self.sample_rate = float(self.config["SampleRate"])

        params = self.config.get("AudioParams", {})

        self.volume = float(params.get("Volume", {}).get("Default", 1.0))
        self.speed = float(params.get("Speed", {}).get("Default", 1.0))
        self.pitch = float(params.get("Pitch", {}).get("Default", 1.0))
        self.proxy = self.config.get("Proxy", "")

        self.started_playing: float | None = None
        self.stopped_playing: float | None = None
        self.seconds: float = 0.0
        self.duration_set: bool = False

        self.writer: StreamWriter | None = None
        self.ffmpeg_process: Process | None = None
        self.stream_task: Task | None = None
        self.session: aiohttp.ClientSession | None = None

        self.callbacks: list[tuple[str, Callable]] = []

    def __del__(self) -> None:
        self.logger.debug("~FFmpegAudioPlayer()")
        self.Stop()

    async def _stream_url_to_ffmpeg(self, uri: str, ffmpeg_command: list[str]) -> None:
        parsed = urlparse(uri)
        is_local_file = parsed.scheme in ("file", "") or os.path.exists(uri)

        if is_local_file:
            file_path = parsed.path if parsed.scheme == "file" else uri

            if "-i" in ffmpeg_command:
                idx = ffmpeg_command.index("-i")
                ffmpeg_command[idx + 1] = file_path
            else:
                ffmpeg_command.extend(["-i", file_path])

        try:
            _, self.writer = await asyncio.open_connection(self.host, self.port)
        except Exception as e:
            self.logger.error("Failed to connect to voice server at %s:%s - %s", self.host, self.port, e)
            self.Stop(False)
            return

        stdin_mode = asyncio.subprocess.DEVNULL if is_local_file else asyncio.subprocess.PIPE

        try:
            self.ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_command, stdin=stdin_mode, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
            )
        except Exception as e:
            self.logger.error("Failed to spawn FFmpeg process: %s", e)
            self.Stop(False)
            return

        if self.ffmpeg_process.stdout:
            asyncio.ensure_future(self._read_stream(self.ffmpeg_process.stdout, self.writer))

        if is_local_file:
            return

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        timeout = aiohttp.ClientTimeout(total=None, connect=10.0, sock_read=15.0)
        bytes_downloaded = 0
        max_network_retries = 5

        try:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()

            proxy_url = self.proxy if self.proxy else None

            for attempt in range(1, max_network_retries + 1):
                if not self.playing or self.ffmpeg_process.returncode is not None:
                    break

                req_headers = headers.copy()
                if bytes_downloaded > 0:
                    req_headers["Range"] = f"bytes={bytes_downloaded}-"

                try:
                    async with self.session.get(uri, headers=req_headers, timeout=timeout, proxy=proxy_url) as resp:
                        if resp.status not in (200, 206):
                            self.logger.error("HTTP stream failed with status %d", resp.status)
                            break

                        async for chunk in resp.content.iter_chunked(32 * 1024):
                            if not self.playing or self.ffmpeg_process.returncode is not None:
                                break

                            bytes_downloaded += len(chunk)

                            if self.ffmpeg_process.stdin:
                                self.ffmpeg_process.stdin.write(chunk)
                                await self.ffmpeg_process.stdin.drain()

                        break

                except (asyncio.TimeoutError, aiohttp.ClientError) as err:
                    self.logger.warning(
                        "Stream network drop/timeout (%s). Retrying (%d/%d)...", err, attempt, max_network_retries
                    )
                    await asyncio.sleep(0.5)

        except Exception as e:
            self.logger.error("Unexpected streaming error: %s", e, exc_info=True)
        finally:
            if self.ffmpeg_process and self.ffmpeg_process.stdin:
                try:
                    self.ffmpeg_process.stdin.close()
                    await self.ffmpeg_process.stdin.wait_closed()
                except Exception as e:
                    self.logger.debug("Failed to cleanly close FFmpeg stdin: %s", e)

    def SetDuration(self, duration: float) -> None:
        self.seconds = duration
        if self.seconds > 0:
            self.duration_set = True

    def PlayURI(
        self,
        uri: str,
        position: int | None,
        duration: int | None,
        *args: Any,
        volume: float | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> bool:
        if volume is None:
            volume = self.volume

        if speed is None:
            speed = self.speed

        if pitch is None:
            pitch = self.pitch

        self.seconds = 0.0
        self.started_playing = None
        self.stopped_playing = None

        ffmpeg_command = [
            "/usr/bin/ffmpeg",
            "-i",
            "pipe:0",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            str(int(self.sample_rate)),
            "-filter:a",
            f"volume={float(volume)},rubberband=tempo={speed}:pitch={pitch}",
            "-f",
            "s16le",
            "-vn",
            *args,
        ]

        if position is not None:
            pos_str = str(datetime.timedelta(seconds=position))
            ffmpeg_command.extend(["-ss", pos_str])
            self.position = position

        if duration is not None:
            ffmpeg_command.extend(["-t", str(duration)])

        ffmpeg_command.append("-")

        self.logger.debug(ffmpeg_command)

        self.playing = True
        self.uri = uri

        self.logger.info("Playing %s", self.uri)

        self.stream_task = asyncio.ensure_future(self._stream_url_to_ffmpeg(uri, ffmpeg_command))
        return True

    def Stop(self, force: bool = True) -> bool:
        if not self.playing:
            return False

        self.playing = False

        if self.stream_task and not self.stream_task.done():
            self.stream_task.cancel()
            self.stream_task = None

        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.kill()
            except ProcessLookupError as exc:
                self.logger.debug(exc)
            self.ffmpeg_process = None

        if self.writer:
            if force:
                writer_socket = self.writer.transport.get_extra_info("socket")
                if writer_socket:
                    try:
                        writer_socket.setsockopt(
                            socket.SOL_SOCKET,
                            socket.SO_LINGER,
                            struct.pack("ii", 1, 0),
                        )
                    except OSError as exc:
                        if exc.errno == 9:
                            self.logger.error("Unable to setsockopt: %s", exc)

                self.writer.transport.abort()

            self.writer.close()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.writer.wait_closed())
                else:
                    loop.run_until_complete(self.writer.wait_closed())
            except Exception as exc:
                self.logger.warning(exc)

            self.writer = None

        self.logger.info("Stopped %s", self.uri)
        self.uri = ""

        self.Callback("Stop")

        return True

    def AddCallback(self, cbtype: str, cbfunc: Callable) -> bool:
        if cbtype not in self.VALID_CALLBACKS:
            return False

        self.callbacks.append((cbtype, cbfunc))
        return True

    def Callback(self, cbtype: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            if callback[0] == cbtype:
                try:
                    self.logger.debug(f"{callback[1]}({args}, {kwargs}")
                    callback[1](*args, **kwargs)
                except Exception:
                    self.logger.error(traceback.format_exc())

    async def _updater(self) -> None:
        try:
            last_seconds_elapsed = 0.0

            while self.playing:
                seconds_elapsed = 0.0

                if self.started_playing:
                    seconds_elapsed = time.time() - self.started_playing

                if self.duration_set and seconds_elapsed > self.seconds:
                    seconds_elapsed = self.seconds

                self.Callback("Update", last_seconds_elapsed, seconds_elapsed)

                is_ffmpeg_done = self.ffmpeg_process is None or self.ffmpeg_process.returncode is not None

                if self.duration_set and self.seconds > 0 and seconds_elapsed >= self.seconds:
                    if is_ffmpeg_done:
                        self.logger.debug("Playback naturally finished (time reached).")
                        self.Stop(False)
                        return

                elif not self.duration_set and is_ffmpeg_done:
                    self.logger.debug("Playback naturally finished (FFmpeg EOF).")
                    self.Stop(False)
                    return

                last_seconds_elapsed = seconds_elapsed
                await asyncio.sleep(0.1)

        except Exception as exc:
            self.Stop()
            self.torchlight.SayChat(f"Error: {str(exc)}")
            raise exc

    async def _read_stream(self, stream: StreamReader, writer: StreamWriter) -> None:
        try:
            started = False

            while stream and self.playing:
                data = await stream.read(65536)
                if not data:
                    break

                if writer is not None:
                    writer.write(data)
                    await writer.drain()

                bytes_len = len(data)
                samples = bytes_len / SAMPLEBYTES
                seconds = samples / self.sample_rate

                if not self.duration_set:
                    self.seconds += seconds

                if not started:
                    self.logger.info("Streaming %s", self.uri)
                    started = True
                    self.Callback("Play")
                    self.started_playing = time.time()
                    asyncio.ensure_future(self._updater())

            self.stopped_playing = time.time()
        except Exception as exc:
            self.Stop()
            self.torchlight.SayChat(f"Error: {str(exc)}")
            raise exc
