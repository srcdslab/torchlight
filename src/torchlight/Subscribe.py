#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import traceback
from typing import Any, Dict, List, Set

from Torchlight import Torchlight


class SubscribeBase:
    def __init__(self, master: Torchlight, module: str):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Torchlight: Torchlight = master
        self.Module = module

        self.Callbacks: Dict[str, Set] = dict()

    def __del__(self) -> None:
        if not len(self.Callbacks) or not self.Torchlight():
            return

        Obj = {
            "method": "unsubscribe",
            "module": self.Module,
            "events": self.Callbacks.keys(),
        }

        asyncio.ensure_future(self.Torchlight().Send(Obj))

    async def _Register(self, events: List[str]) -> List[bool]:
        Obj = {"method": "subscribe", "module": self.Module, "events": events}

        Res = await self.Torchlight().Send(Obj)

        Ret: List[bool] = []
        for i, ret in enumerate(Res["events"]):
            if ret >= 0:
                Ret.append(True)
                if not events[i] in self.Callbacks:
                    self.Callbacks[events[i]] = set()
            else:
                Ret.append(False)

        return Ret

    async def _Unregister(self, events: List[str]) -> List[bool]:

        Obj = {"method": "unsubscribe", "module": self.Module, "events": events}

        Res = await self.Torchlight().Send(Obj)

        Ret: List[bool] = []
        for i, ret in enumerate(Res["events"]):
            if ret >= 0:
                Ret.append(True)
                if events[i] in self.Callbacks:
                    del self.Callbacks[events[i]]
            else:
                Ret.append(False)

        return Ret

    def HookEx(self, event: str, callback: function) -> None:
        asyncio.ensure_future(self.Hook(event, callback))

    def UnhookEx(self, event: str, callback: function) -> None:
        asyncio.ensure_future(self.Unhook(event, callback))

    def ReplayEx(self, events: List[str]) -> None:
        asyncio.ensure_future(self.Replay(events))

    async def Hook(self, event: str, callback: function) -> bool:
        if not event in self.Callbacks:
            if not (await self._Register([event]))[0]:
                return False

        self.Callbacks[event].add(callback)
        return True

    async def Unhook(self, event: str, callback: function) -> bool:
        if not event in self.Callbacks:
            return True

        if not callback in self.Callbacks[event]:
            return True

        self.Callbacks[event].discard(callback)

        if len(a) == 0:
            return (await self._Unregister([event]))[0]

        return True

    async def Replay(self, events: List[str]) -> List[bool]:
        for event in events[:]:
            if not event in self.Callbacks:
                events.remove(event)

        Obj = {"method": "replay", "module": self.Module, "events": events}

        Res = await self.Torchlight().Send(Obj)

        Ret: List[bool] = []
        for i, ret in enumerate(Res["events"]):
            if ret >= 0:
                Ret.append(True)
            else:
                Ret.append(False)

        return Ret

    def OnPublish(self, obj: Dict[str, Any]) -> bool:
        Event = obj["event"]

        if not Event["name"] in self.Callbacks:
            return False

        Callbacks = self.Callbacks[Event["name"]]

        for Callback in Callbacks:
            try:
                Callback(**Event["data"])
            except Exception:
                self.Logger.error(traceback.format_exc())
                self.Logger.error(Event)

        return True


class GameEvents(SubscribeBase):
    def __init__(self, master: Torchlight):
        super().__init__(master, "gameevents")


class Forwards(SubscribeBase):
    def __init__(self, master: Torchlight):
        super().__init__(master, "forwards")
