import asyncio
import logging
import traceback
from collections.abc import Callable
from typing import Any

from torchlight.AsyncClient import AsyncClient


class SubscribeBase:
    def __init__(self, async_client: AsyncClient):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.module = self.__class__.__name__.lower()
        self.async_client = async_client

        self.callbacks: dict[str, set[Callable]] = {}

    def __del__(self) -> None:
        if not len(self.callbacks) or not self.async_client:
            return

        json_obj = {
            "method": "unsubscribe",
            "module": self.module,
            "events": self.callbacks.keys(),
        }

        asyncio.ensure_future(self.async_client.Send(json_obj))

    async def _Register(self, events: list[str]) -> list[bool]:
        json_obj = {
            "method": "subscribe",
            "module": self.module,
            "events": events,
        }

        res_raw = await self.async_client.Send(json_obj)

        res: dict[str, Any] = {}
        if isinstance(res_raw, dict):
            res = res_raw

        ret_list: list[bool] = []
        for i, ret in enumerate(res.get("events", [])):
            if ret >= 0:
                ret_list.append(True)
                if events[i] not in self.callbacks:
                    self.callbacks[events[i]] = set()
            else:
                ret_list.append(False)

        return ret_list

    async def _Unregister(self, events: list[str]) -> list[bool]:
        json_obj = {
            "method": "unsubscribe",
            "module": self.module,
            "events": events,
        }

        res_raw = await self.async_client.Send(json_obj)

        res: dict[str, Any] = {}
        if isinstance(res_raw, dict):
            res = res_raw

        ret_list: list[bool] = []
        for i, ret in enumerate(res["events"]):
            if ret >= 0:
                ret_list.append(True)
                if events[i] in self.callbacks:
                    del self.callbacks[events[i]]
            else:
                ret_list.append(False)

        return ret_list

    def HookEx(self, event: str, callback: Callable) -> None:
        asyncio.ensure_future(self.Hook(event, callback))

    def UnhookEx(self, event: str, callback: Callable) -> None:
        asyncio.ensure_future(self.Unhook(event, callback))

    def ReplayEx(self, events: list[str]) -> None:
        asyncio.ensure_future(self.Replay(events))

    async def Hook(self, event: str, callback: Callable) -> bool:
        if event not in self.callbacks:
            ret = await self._Register([event])
            if not ret or not ret[0]:
                return False

        self.callbacks[event].add(callback)
        return True

    async def Unhook(self, event: str, callback: Callable) -> bool:
        if event not in self.callbacks:
            return True

        if callback not in self.callbacks[event]:
            return True

        self.callbacks[event].discard(callback)

        return (await self._Unregister([event]))[0]

    async def Replay(self, events: list[str]) -> list[bool]:
        for event in events[:]:
            if event not in self.callbacks:
                events.remove(event)

        json_obj = {"method": "replay", "module": self.module, "events": events}

        res_raw = await self.async_client.Send(json_obj)

        res: dict[str, Any] = {}
        if isinstance(res_raw, dict):
            res = res_raw

        ret_list: list[bool] = []
        for _, ret in enumerate(res["events"]):
            if ret >= 0:
                ret_list.append(True)
            else:
                ret_list.append(False)

        return ret_list

    def OnPublish(self, json_obj: dict[str, Any]) -> bool:
        event = json_obj["event"]

        if event["name"] not in self.callbacks:
            return False

        callbacks = self.callbacks[event["name"]]

        for callback in callbacks:
            try:
                callback(**event["data"])
            except Exception:
                self.logger.error(traceback.format_exc())
                self.logger.error(event)

        return True


class GameEvents(SubscribeBase):
    def __init__(self, async_client: AsyncClient) -> None:
        super().__init__(async_client)


class Forwards(SubscribeBase):
    def __init__(self, async_client: AsyncClient) -> None:
        super().__init__(async_client)
