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
        self.position: int = 0

        self.host = self.config["Host"]
        self.port = self.config["Port"]
        self.sample_rate = float(self.config["SampleRate"])

        self.started_playing: float | None = None
        self.stopped_playing: float | None = None
        self.seconds = 0.0

        self.writer: StreamWriter | None = None
        self.sub_process: Process | None = None

        self.callbacks: list[tuple[str, Callable]] = []

    def __del__(self) -> None:
        self.logger.debug("~FFmpegAudioPlayer()")
        self.Stop()

    def PlayURI(self, uri: str, position: int | None, *args: Any) -> bool:
        if position is not None:
            pos_str = str(datetime.timedelta(seconds=position))
            command = [
                "/usr/bin/ffmpeg",
                "-ss",
                pos_str,
                "-i",
                uri,
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                str(int(self.sample_rate)),
                "-f",
                "s16le",
                "-vn",
                *args,
                "-",
            ]
            self.position = position
        else:
            command = [
                "/usr/bin/ffmpeg",
                "-i",
                uri,
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                str(int(self.sample_rate)),
                "-f",
                "s16le",
                "-vn",
                *args,
                "-",
            ]

        print(command)

        self.playing = True
        asyncio.ensure_future(self._stream_subprocess(command))
        return True

    def Stop(self, force: bool = True) -> bool:
        if not self.playing:
            return False

        if self.sub_process:
            try:
                self.sub_process.terminate()
                self.sub_process.kill()
                self.sub_process = None
            except ProcessLookupError:
                pass

        if self.writer:
            if force:
                writer_socket = self.writer.transport.get_extra_info("socket")
                if writer_socket:
                    writer_socket.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_LINGER,
                        struct.pack("ii", 1, 0),
                    )

                self.writer.transport.abort()

            self.writer.close()

        self.playing = False

        self.Callback("Stop")
        del self.callbacks

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
                    callback[1](*args, **kwargs)
                except Exception:
                    self.logger.error(traceback.format_exc())

    async def _updater(self) -> None:
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
                    print("BUFFER UNDERRUN!")
                self.Stop(False)
                return

            last_seconds_elapsed = seconds_elapsed

            await asyncio.sleep(0.1)

    async def _read_stream(
        self, stream: StreamReader | None, writer: StreamWriter
    ) -> None:
        started = False

        while stream and self.playing:
            data = await stream.read(65536)

            if data:
                writer.write(data)
                await writer.drain()

                bytes_len = len(data)
                samples = bytes_len / SAMPLEBYTES
                seconds = samples / self.sample_rate

                self.seconds += seconds

                if not started:
                    started = True
                    self.Callback("Play")
                    self.started_playing = time.time()
                    asyncio.ensure_future(self._updater())
            else:
                self.sub_process = None
                break

        self.stopped_playing = time.time()

    async def _stream_subprocess(self, cmd: list[str]) -> None:
        if not self.playing:
            return

        _, self.writer = await asyncio.open_connection(self.host, self.port)

        self.sub_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await self._read_stream(self.sub_process.stdout, self.writer)
        if self.sub_process is not None:
            await self.sub_process.wait()

        if self.seconds == 0.0:
            self.Stop()
