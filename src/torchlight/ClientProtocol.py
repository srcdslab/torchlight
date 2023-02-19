#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import traceback
from asyncio import AbstractEventLoop, Protocol, transports
from typing import Any, Callable, List, Optional, Tuple


class ClientProtocol(Protocol):
    VALID_CALLBACKS = ["OnReceive", "OnDisconnect"]

    def __init__(self, loop: AbstractEventLoop):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Loop = loop
        self.Transport: Optional[transports.WriteTransport] = None
        self.Buffer = bytearray()
        self.Callbacks: List[Tuple[str, Callable]] = []

    def connection_made(self, transport: transports.WriteTransport) -> None:  # type: ignore[override]
        self.Transport = transport

    def data_received(self, data: bytes) -> None:
        self.Buffer += data

        chunks = self.Buffer.split(b"\0")
        if data[-1] == b"\0":
            chunks = chunks[:-1]
            self.Buffer = bytearray()
        else:
            self.Buffer = bytearray(chunks[-1])
            chunks = chunks[:-1]

        for chunk in chunks:
            self.Callback("OnReceive", chunk)

    def AddCallback(self, cbtype: str, cbfunc: Callable) -> bool:
        if cbtype not in self.VALID_CALLBACKS:
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

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if self.Transport:
            self.Transport.close()
        self.Transport = None
        self.Callback("OnDisconnect", exc)

    def Send(self, data: bytes) -> None:
        if self.Transport:
            self.Transport.write(data)
