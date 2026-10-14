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
    # Seconds to wait for SourceMod to answer one request before the link is considered broken.
    SEND_TIMEOUT = 10.0

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
        self.recv_future: Future[Any] | None = None
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

        if isinstance(json_obj, dict) and json_obj.get("method") == "publish":
            self.Callback("OnPublish", json_obj)
            return

        future = self.recv_future
        if future is None or future.done():
            # No request is waiting (it timed out or was cancelled) or it was already answered.
            self.logger.warning("OnReceive: Unexpected reply with no pending request, dropping it")
            return

        future.set_result(json_obj)

    def OnDisconnect(self, exc: Exception | None) -> None:
        self.protocol = None
        if self.recv_future and not self.recv_future.done():
            self.recv_future.cancel()
        self.Callback("OnDisconnect", exc)

    async def Send(self, json_obj: Any) -> Any | None:
        if not self.protocol:
            return None

        data = json.dumps(json_obj, ensure_ascii=False, separators=(",", ":")).encode("UTF-8")

        async with self.send_lock:
            if not self.protocol:
                return None

            future: Future[Any] = self.loop.create_future()
            self.recv_future = future
            self.protocol.Send(data)

            try:
                await asyncio.wait_for(future, timeout=self.SEND_TIMEOUT)
            except TimeoutError:
                self.logger.warning(
                    f"Send: No reply to {self._Describe(json_obj)} within {self.SEND_TIMEOUT}s, "
                    "dropping the SourceMod link"
                )
                self._DropConnection()
                return None
            except asyncio.CancelledError:
                return None
            finally:
                self.recv_future = None

            return future.result()

    def _DropConnection(self) -> None:
        # Requests carry no id, so a late reply would be matched to the next request.
        # Close the link instead: connection_lost -> OnDisconnect -> reconnect takes over.
        protocol = self.protocol
        self.protocol = None
        if protocol:
            protocol.Close()

    @staticmethod
    def _Describe(json_obj: Any) -> str:
        if not isinstance(json_obj, dict):
            return "request"
        method = json_obj.get("method")
        target = json_obj.get("function") or json_obj.get("module")
        return f"{method}({target})" if target else str(method)
