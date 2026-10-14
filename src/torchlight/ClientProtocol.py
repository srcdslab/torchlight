import logging
import traceback
from asyncio import AbstractEventLoop, Protocol, transports
from collections.abc import Callable
from typing import Any


class ClientProtocol(Protocol):
    VALID_CALLBACKS = ["OnReceive", "OnDisconnect"]
    # Largest partial message kept while waiting for its NUL terminator.
    MAX_BUFFER_SIZE = 4 * 1024 * 1024

    def __init__(self, loop: AbstractEventLoop):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop = loop
        self.transport: transports.WriteTransport | None = None
        self.buffer = bytearray()
        self.callbacks: list[tuple[str, Callable]] = []

    def connection_made(self, transport: transports.WriteTransport) -> None:  # type: ignore[override]
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        if self.transport is None or self.transport.is_closing():
            return

        self.buffer += data

        # Only the new data can complete a message: the buffered prefix never holds a NUL.
        if b"\0" in data:
            *chunks, rest = self.buffer.split(b"\0")
            self.buffer = bytearray(rest)

            for chunk in chunks:
                if chunk:
                    self.Callback("OnReceive", bytes(chunk))

        if len(self.buffer) > self.MAX_BUFFER_SIZE:
            self.logger.error(
                f"data_received: {len(self.buffer)} bytes buffered without a NUL terminator, closing the connection"
            )
            self.Close()

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
        self.buffer = bytearray()
        self.Callback("OnDisconnect", exc)

    def Send(self, data: bytes) -> None:
        if self.transport:
            self.transport.write(data)

    def Close(self) -> None:
        # connection_lost (and so OnDisconnect) runs once the transport is closed.
        self.buffer = bytearray()
        if self.transport:
            self.transport.close()
