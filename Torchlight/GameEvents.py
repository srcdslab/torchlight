#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio

class GameEvents():
	def __init__(self, master):
		self.Torchlight = master

		self.Callbacks = {}

	def __del__(self):
		if not len(self.Callbacks) or not self.Torchlight():
			return

		Obj = {
			"method": "unsubscribe",
			"module": "gameevents",
			"events": self.Callbacks.keys()
		}

		asyncio.ensure_future(self.Torchlight().Send(Obj))

	async def _Register(self, events):
		if type(events) is not list:
			events = [ events ]

		Obj = {
			"method": "subscribe",
			"module": "gameevents",
			"events": events
		}

		Res = await self.Torchlight().Send(Obj)

		Ret = []
		for i, ret in enumerate(Res["events"]):
			if ret >= 0:
				Ret.append(True)
				if not events[i] in self.Callbacks:
					self.Callbacks[events[i]] = set()
			else:
				Ret.append(False)

		if len(Ret) == 1:
			Ret = Ret[0]
		return Ret

	async def _Unregister(self, events):
		if type(events) is not list:
			events = [ events ]

		Obj = {
			"method": "unsubscribe",
			"module": "gameevents",
			"events": events
		}

		Res = await self.Torchlight().Send(Obj)

		Ret = []
		for i, ret in enumerate(Res["events"]):
			if ret >= 0:
				Ret.append(True)
				if events[i] in self.Callbacks:
					del self.Callbacks[events[i]]
			else:
				Ret.append(False)

		if len(Ret) == 1:
			Ret = Ret[0]
		return Ret

	def HookEx(self, event, callback):
		asyncio.ensure_future(self.Hook(event, callback))

	def UnhookEx(self, event, callback):
		asyncio.ensure_future(self.Unhook(event, callback))

	def ReplayEx(self, events):
		asyncio.ensure_future(self.Replay(events))

	async def Hook(self, event, callback):
		if not event in self.Callbacks:
			if not await self._Register(event):
				return False

		self.Callbacks[event].add(callback)
		return True

	async def Unhook(self, event, callback):
		if not event in self.Callbacks:
			return True

		if not callback in self.Callbacks[event]:
			return True

		self.Callbacks[event].discard(callback)

		if len(a) == 0:
			return await self._Unregister(event)

		return True

	async def Replay(self, events):
		if type(events) is not list:
			events = [ events ]

		for event in events[:]:
			if not event in self.Callbacks:
				events.remove(event)

		Obj = {
			"method": "replay",
			"module": "gameevents",
			"events": events
		}

		Res = await self.Torchlight().Send(Obj)

		Ret = []
		for i, ret in enumerate(Res["events"]):
			if ret >= 0:
				Ret.append(True)
			else:
				Ret.append(False)

		if len(Ret) == 1:
			Ret = Ret[0]
		return Ret

	def OnPublish(self, obj):
		Event = obj["event"]

		if not Event["name"] in self.Callbacks:
			return False

		Callbacks = self.Callbacks[Event["name"]]

		for Callback in Callbacks:
			Callback(**Event["data"])

		return True
