#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import datetime
import logging
import socket
import struct
import time
import traceback
from asyncio import StreamReader, StreamWriter
from asyncio.subprocess import Process
from typing import Any, Callable, List, Optional, Tuple

from torchlight.Torchlight import Torchlight

SAMPLEBYTES = 2


class FFmpegAudioPlayer:
    VALID_CALLBACKS = ["Play", "Stop", "Update"]

    def __init__(self, torchlight: Torchlight) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.config = self.torchlight.config["VoiceServer"]
        self.Playing = False
        self.Position: int = 0

        self.host = self.config["Host"]
        self.port = self.config["Port"]
        self.sample_rate = float(self.config["SampleRate"])

        self.StartedPlaying: Optional[float] = None
        self.StoppedPlaying: Optional[float] = None
        self.Seconds = 0.0

        self.Writer: Optional[StreamWriter] = None
        self.sub_process: Optional[Process] = None

        self.Callbacks: List[Tuple[str, Callable]] = []

    def __del__(self) -> None:
        self.Logger.debug("~FFmpegAudioPlayer()")
        self.Stop()

    def PlayURI(self, uri: str, position: Optional[int], *args: Any) -> bool:
        if position is not None:
            PosStr = str(datetime.timedelta(seconds=position))
            Command = [
                "/usr/bin/ffmpeg",
                "-ss",
                PosStr,
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
            self.Position = position
        else:
            Command = [
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

        print(Command)

        self.Playing = True
        asyncio.ensure_future(self._stream_subprocess(Command))
        return True

    def Stop(self, force: bool = True) -> bool:
        if not self.Playing:
            return False

        if self.sub_process:
            try:
                self.sub_process.terminate()
                self.sub_process.kill()
                self.sub_process = None
            except ProcessLookupError:
                pass

        if self.Writer:
            if force:
                Socket = self.Writer.transport.get_extra_info("socket")
                if Socket:
                    Socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                    )

                self.Writer.transport.abort()

            self.Writer.close()

        self.Playing = False

        self.Callback("Stop")
        del self.Callbacks

        return True

    def AddCallback(self, cbtype: str, cbfunc: Callable) -> bool:
        if not cbtype in self.VALID_CALLBACKS:
            return False

        self.Callbacks.append((cbtype, cbfunc))
        return True

    def Callback(self, cbtype: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.Callbacks:
            if callback[0] == cbtype:
                try:
                    callback[1](*args, **kwargs)
                except Exception:
                    self.Logger.error(traceback.format_exc())

    async def _updater(self) -> None:
        LastSecondsElapsed = 0.0

        while self.Playing:
            SecondsElapsed = 0.0

            if self.StartedPlaying:
                SecondsElapsed = time.time() - self.StartedPlaying

            if SecondsElapsed > self.Seconds:
                SecondsElapsed = self.Seconds

            self.Callback("Update", LastSecondsElapsed, SecondsElapsed)

            if SecondsElapsed >= self.Seconds:
                if not self.StoppedPlaying:
                    print("BUFFER UNDERRUN!")
                self.Stop(False)
                return

            LastSecondsElapsed = SecondsElapsed

            await asyncio.sleep(0.1)

    async def _read_stream(
        self, stream: Optional[StreamReader], writer: StreamWriter
    ) -> None:
        Started = False

        while stream and self.Playing:
            Data = await stream.read(65536)

            if Data:
                writer.write(Data)
                await writer.drain()

                Bytes = len(Data)
                Samples = Bytes / SAMPLEBYTES
                Seconds = Samples / self.sample_rate

                self.Seconds += Seconds

                if not Started:
                    Started = True
                    self.Callback("Play")
                    self.StartedPlaying = time.time()
                    asyncio.ensure_future(self._updater())
            else:
                self.sub_process = None
                break

        self.StoppedPlaying = time.time()

    async def _stream_subprocess(self, cmd: List[str]) -> None:
        if not self.Playing:
            return

        _, self.Writer = await asyncio.open_connection(self.host, self.port)

        self.sub_process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )

        await self._read_stream(self.sub_process.stdout, self.Writer)
        if self.sub_process is not None:
            await self.sub_process.wait()

        if self.Seconds == 0.0:
            self.Stop()
