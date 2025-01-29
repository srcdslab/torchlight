import asyncio
import datetime
import logging
import socket
import struct
import time
import traceback
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process
from collections.abc import Callable
from typing import Any

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
        self.volume = float(self.config["Volume"])
        self.proxy = self.config.get("Proxy", "")

        self.started_playing: float | None = None
        self.stopped_playing: float | None = None
        self.seconds = 0.0

        self.writer: StreamWriter | None = None
        self.ffmpeg_process: Process | None = None
        self.curl_process: Process | None = None

        self.callbacks: list[tuple[str, Callable]] = []

    def __del__(self) -> None:
        self.logger.debug("~FFmpegAudioPlayer()")
        self.Stop()

    # @profile
    def PlayURI(self, uri: str, position: int | None, *args: Any) -> bool:
        curl_command = [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "1",
            "--retry",
            "2",
            "--retry-delay",
            "1",
            "--output",
            "-",
            "-L",
            uri,
        ]
        if self.proxy:
            curl_command.extend(
                [
                    "-x",
                    self.proxy,
                ]
            )
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
            f"volume={str(float(self.volume))}",
            "-f",
            "s16le",
            "-vn",
            *args,
            "-",
        ]

        if position is not None:
            pos_str = str(datetime.timedelta(seconds=position))
            ffmpeg_command.extend(
                [
                    "-ss",
                    pos_str,
                ]
            )
            self.position = position

        self.logger.debug(curl_command)
        self.logger.debug(ffmpeg_command)

        self.playing = True
        self.uri = uri

        self.logger.info("Playing %s", self.uri)

        asyncio.ensure_future(self._stream_subprocess(curl_command, ffmpeg_command))
        return True

    # @profile
    def Stop(self, force: bool = True) -> bool:
        if not self.playing:
            return False

        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.kill()
            except ProcessLookupError as exc:
                self.logger.debug(exc)
            self.ffmpeg_process = None

        if self.curl_process:
            try:
                self.curl_process.terminate()
                self.curl_process.kill()
            except ProcessLookupError as exc:
                self.logger.debug(exc)
            self.curl_process = None

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
                        # Errno 9: Bad file descriptor
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

        self.playing = False
        self.uri = ""

        self.Callback("Stop")
        del self.callbacks

        return True

    # @profile
    def AddCallback(self, cbtype: str, cbfunc: Callable) -> bool:
        if cbtype not in self.VALID_CALLBACKS:
            return False

        self.callbacks.append((cbtype, cbfunc))
        return True

    # @profile
    def Callback(self, cbtype: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            if callback[0] == cbtype:
                try:
                    self.logger.debug(f"{callback[1]}({args}, {kwargs}")
                    callback[1](*args, **kwargs)
                except Exception:
                    self.logger.error(traceback.format_exc())

    # @profile
    async def _updater(self) -> None:
        try:
            last_seconds_elapsed = 0.0

            while self.playing:
                seconds_elapsed = 0.0

                if self.started_playing:
                    seconds_elapsed = time.time() - self.started_playing

                if seconds_elapsed > self.seconds:
                    seconds_elapsed = self.seconds

                self.Callback("Update", last_seconds_elapsed, seconds_elapsed)

                if seconds_elapsed >= self.seconds:
                    if not self.stopped_playing:
                        self.logger.debug("BUFFER UNDERRUN!")
                    self.Stop(False)
                    return

                last_seconds_elapsed = seconds_elapsed

                await asyncio.sleep(0.1)
        except Exception as exc:
            self.Stop()
            self.torchlight.SayChat(f"Error: {str(exc)}")
            raise exc

    # @profile
    async def _read_stream(self, stream: StreamReader | None, writer: StreamWriter) -> None:
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

    # @profile
    async def _stream_subprocess(self, curl_command: list[str], ffmpeg_command: list[str]) -> None:
        if not self.playing:
            return

        try:
            _, self.writer = await asyncio.open_connection(self.host, self.port)

            self.curl_process = await asyncio.create_subprocess_exec(
                *curl_command,
                stdout=asyncio.subprocess.PIPE,
            )

            self.ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            asyncio.create_task(self._wait_for_process_exit(self.curl_process))

            asyncio.create_task(self._write_stream(self.curl_process.stdout, self.ffmpeg_process.stdin))

            asyncio.create_task(self._read_stream(self.ffmpeg_process.stdout, self.writer))

            if self.ffmpeg_process is not None:
                await self.ffmpeg_process.wait()

            if self.seconds == 0.0:
                self.Stop()

        except Exception as exc:
            self.Stop()
            self.torchlight.SayChat(f"Error: {str(exc)}")
            raise exc

    async def _write_stream(self, stream: StreamReader | None, writer: StreamWriter | None) -> None:
        try:
            while True:
                if not stream:
                    break
                chunk = await stream.read(65536)
                if not chunk:
                    break

                if writer:
                    writer.write(chunk)
                    await writer.drain()
            if writer:
                writer.close()
        except Exception as exc:
            self.Stop()
            self.torchlight.SayChat(f"Error: {str(exc)}")
            raise exc

    async def _wait_for_process_exit(self, curl_process: Process) -> None:
        try:
            await curl_process.wait()
            if curl_process.returncode != 0 and curl_process.returncode != -15:
                raise Exception(f"Curl process exited with error code {curl_process.returncode}")
        except Exception as exc:
            self.Stop()
            self.torchlight.SayChat(f"Error: {str(exc)}")
            raise exc
