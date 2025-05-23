import asyncio
import json
import logging
import traceback
from asyncio import Future
from collections.abc import Callable
from typing import Any

from torchlight.ClientProtocol import ClientProtocol


class AsyncClient:
    VALID_CALLBACKS = ["OnPublish", "OnDisconnect"]

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        smapi_server_config: dict[str, Any],
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop: asyncio.AbstractEventLoop = loop
        self.smapi_server_config: dict[str, Any] = smapi_server_config

        self.host = self.smapi_server_config["Host"]
        self.port = self.smapi_server_config["Port"]

        self.protocol: ClientProtocol | None = None
        self.send_lock = asyncio.Lock()
        self.recv_future: Future | None = None
        self.callbacks: list[tuple[str, Callable]] = []

    # @profile
    async def Connect(self) -> None:
        while True:
            self.logger.warning("Reconnecting...")
            try:
                _, self.protocol = await self.loop.create_connection(
                    lambda: ClientProtocol(self.loop),
                    host=self.host,
                    port=self.port,
                )
                self.protocol.AddCallback("OnReceive", self.OnReceive)
                self.protocol.AddCallback("OnDisconnect", self.OnDisconnect)
                break
            except Exception:
                await asyncio.sleep(1.0)

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

    def OnReceive(self, data: str | bytes) -> None:
        try:
            json_obj = json.loads(data)
        except Exception:
            self.logger.warning("OnReceive: Unable to decode data as json, skipping")
            return

        if "method" in json_obj and json_obj["method"] == "publish":
            self.Callback("OnPublish", json_obj)
        else:
            if self.recv_future:
                self.recv_future.set_result(json_obj)

    def OnDisconnect(self, exc: Exception | None) -> None:
        self.protocol = None
        if self.recv_future:
            self.recv_future.cancel()
        self.Callback("OnDisconnect", exc)

    async def Send(self, json_obj: Any) -> Any | None:
        if not self.protocol:
            return None

        data = json.dumps(json_obj, ensure_ascii=False, separators=(",", ":")).encode("UTF-8")

        async with self.send_lock:
            if not self.protocol:
                return None

            self.recv_future = Future()
            self.protocol.Send(data)
            await self.recv_future

            if self.recv_future.done():
                json_obj = self.recv_future.result()
            else:
                json_obj = None

            self.recv_future = None
            return json_obj
