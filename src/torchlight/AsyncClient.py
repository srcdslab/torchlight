#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import json
import logging
from asyncio import AbstractEventLoop, Future, Protocol, transports
from typing import Any, Optional, Union

from Torchlight import TorchlightHandler


class ClientProtocol(Protocol):
    def __init__(self, loop: AbstractEventLoop, master: AsyncClient):
        self.Loop = loop
        self.Master: AsyncClient = master
        self.Transport: Optional[transports.BaseTransport] = None
        self.Buffer = bytearray()

    def connection_made(self, transport: transports.BaseTransport) -> None:
        self.Transport = transport

    def data_received(self, data: bytes) -> None:
        self.Buffer += data

        chunks = self.Buffer.split(b'\0')
        if data[-1] == b'\0':
            chunks = chunks[:-1]
            self.Buffer = bytearray()
        else:
            self.Buffer = bytearray(chunks[-1])
            chunks = chunks[:-1]

        for chunk in chunks:
            self.Master.OnReceive(chunk)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if self.Transport:
            self.Transport.close()
        self.Transport = None
        self.Master.OnDisconnect(exc)

    def Send(self, data: bytes) -> None:
        if self.Transport:
            self.Transport.write(data)


class AsyncClient:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        host: str,
        port: int,
        master: TorchlightHandler,
    ):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Loop: asyncio.AbstractEventLoop = loop
        self.Host = host
        self.Port = port
        self.Master = master

        self.Protocol: Optional[ClientProtocol] = None
        self.SendLock = asyncio.Lock()
        self.RecvFuture: Optional[Future] = None

    async def Connect(self) -> None:
        while True:
            self.Logger.warn("Reconnecting...")
            try:
                _, self.Protocol = await self.Loop.create_connection(
                    lambda: ClientProtocol(self.Loop, self),
                    host=self.Host,
                    port=self.Port,
                )
                break
            except:
                await asyncio.sleep(1.0)

    def OnReceive(self, data: Union[str, bytes]) -> None:
        Obj = json.loads(data)

        if "method" in Obj and Obj["method"] == "publish":
            self.Master.OnPublish(Obj)
        else:
            if self.RecvFuture:
                self.RecvFuture.set_result(Obj)

    def OnDisconnect(self, exc: Optional[Exception]) -> None:
        self.Protocol = None
        if self.RecvFuture:
            self.RecvFuture.cancel()
        self.Master.OnDisconnect(exc)

    async def Send(self, obj: Any) -> Optional[Any]:
        if not self.Protocol:
            return None

        Data = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(
            "UTF-8"
        )

        async with self.SendLock:
            if not self.Protocol:
                return None

            self.RecvFuture = Future()
            self.Protocol.Send(Data)
            await self.RecvFuture

            if self.RecvFuture.done():
                Obj = self.RecvFuture.result()
            else:
                Obj = None

            self.RecvFuture = None
            return Obj
