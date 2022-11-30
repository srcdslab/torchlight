#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import traceback
from asyncio import Future
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from torchlight.ClientProtocol import ClientProtocol


class AsyncClient:
    VALID_CALLBACKS = ["OnPublish", "OnDisconnect"]

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        SMAPIServerConfig: Dict[str, Any],
    ):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Loop: asyncio.AbstractEventLoop = loop
        self.SMAPIServerConfig: Dict[str, Any] = SMAPIServerConfig

        self.Host = self.SMAPIServerConfig["Host"]
        self.Port = self.SMAPIServerConfig["Port"]

        self.Protocol: Optional[ClientProtocol] = None
        self.SendLock = asyncio.Lock()
        self.RecvFuture: Optional[Future] = None
        self.Callbacks: List[Tuple[str, Callable]] = []

    async def Connect(self) -> None:
        while True:
            self.Logger.warn("Reconnecting...")
            try:
                _, self.Protocol = await self.Loop.create_connection(
                    lambda: ClientProtocol(self.Loop),
                    host=self.Host,
                    port=self.Port,
                )
                self.Protocol.AddCallback("OnReceive", self.OnReceive)
                self.Protocol.AddCallback("OnDisconnect", self.OnDisconnect)
                break
            except:
                await asyncio.sleep(1.0)

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

    def OnReceive(self, data: Union[str, bytes]) -> None:
        try:
            Obj = json.loads(data)
        except Exception:
            self.Logger.warn("OnReceive: Unable to decode data as json, skipping")
            return

        if "method" in Obj and Obj["method"] == "publish":
            self.Callback("OnPublish", Obj)
        else:
            if self.RecvFuture:
                self.RecvFuture.set_result(Obj)

    def OnDisconnect(self, exc: Optional[Exception]) -> None:
        self.Protocol = None
        if self.RecvFuture:
            self.RecvFuture.cancel()
        self.Callback("OnDisconnect", exc)

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
