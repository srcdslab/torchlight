import logging
import traceback
from asyncio import AbstractEventLoop, Protocol, transports
from collections.abc import Callable
from typing import Any


class ClientProtocol(Protocol):
    VALID_CALLBACKS = ["OnReceive", "OnDisconnect"]

    def __init__(self, loop: AbstractEventLoop):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop = loop
        self.transport: transports.WriteTransport | None = None
        self.buffer = bytearray()
        self.callbacks: list[tuple[str, Callable]] = []

    def connection_made(self, transport: transports.WriteTransport) -> None:  # type: ignore[override]
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        self.buffer += data

        chunks = self.buffer.split(b"\0")
        if data[-1] == b"\0":
            chunks = chunks[:-1]
            self.buffer = bytearray()
        else:
            self.buffer = bytearray(chunks[-1])
            chunks = chunks[:-1]

        for chunk in chunks:
            self.Callback("OnReceive", chunk)

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

    def connection_lost(self, exc: Exception | None) -> None:
        if self.transport:
            self.transport.close()
        self.transport = None
        self.Callback("OnDisconnect", exc)

    def Send(self, data: bytes) -> None:
        if self.transport:
            self.transport.write(data)
