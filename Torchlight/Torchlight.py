#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import sys
import json
import time
import weakref
import traceback
import textwrap

from .AsyncClient import AsyncClient

from .SourceModAPI import SourceModAPI
from .Subscribe import GameEvents, Forwards

from .Utils import Utils
from .Config import Config
from .CommandHandler import CommandHandler
from .AccessManager import AccessManager
from .PlayerManager import PlayerManager
from .AudioManager import AudioManager

class Torchlight():
	def __init__(self, master):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Master = master
		self.Config = self.Master.Config
		self.WeakSelf = weakref.ref(self)

		self.API = SourceModAPI(self.WeakSelf)
		self.GameEvents = GameEvents(self.WeakSelf)
		self.Forwards = Forwards(self.WeakSelf)

		self.DisableVotes = set()
		self.Disabled = 0
		self.LastUrl = None

	def InitModules(self):
		self.Access = AccessManager()
		self.Access.Load()

		self.Players = PlayerManager(self.WeakSelf)

		self.AudioManager = AudioManager(self.WeakSelf)

		self.CommandHandler = CommandHandler(self.WeakSelf)
		self.CommandHandler.Setup()

		self.GameEvents.HookEx("server_spawn", self.Event_ServerSpawn)
		self.GameEvents.HookEx("player_say", self.Event_PlayerSay)

	def SayChat(self, message, player=None):
		message = "\x0700FFFA[Torchlight]: \x01{0}".format(message)
		if len(message) > 976:
			message = message[:973] + "..."
		lines = textwrap.wrap(message, 244, break_long_words = True)
		for line in lines:
			asyncio.ensure_future(self.API.PrintToChatAll(line))

		if player:
			Level = 0
			if player.Access:
				Level = player.Access["level"]

			if Level < self.Config["AntiSpam"]["ImmunityLevel"]:
				cooldown = len(lines) * self.Config["AntiSpam"]["ChatCooldown"]
				if player.ChatCooldown > self.Master.Loop.time():
					player.ChatCooldown += cooldown
				else:
					player.ChatCooldown = self.Master.Loop.time() + cooldown

	def SayPrivate(self, player, message):
		message = "\x0700FFFA[Torchlight]: \x01{0}".format(message)
		if len(message) > 976:
			message = message[:973] + "..."
		lines = textwrap.wrap(message, 244, break_long_words = True)
		for line in lines:
			asyncio.ensure_future(self.API.PrintToChat(player.Index, line))

	def Reload(self):
		self.Config.Load()
		self.CommandHandler.NeedsReload = True

	async def Send(self, data):
		return await self.Master.Send(data)

	def OnPublish(self, obj):
		if obj["module"] == "gameevents":
			self.GameEvents.OnPublish(obj)
		elif obj["module"] == "forwards":
			self.Forwards.OnPublish(obj)

	def Event_ServerSpawn(self, hostname, address, ip, port, game, mapname, maxplayers, os, dedicated, password):
		self.DisableVotes = set()
		self.Disabled = 0

	def Event_PlayerSay(self, userid, text):
		if userid == 0:
			return

		Player = self.Players.FindUserID(userid)
		asyncio.ensure_future(self.CommandHandler.HandleCommand(text, Player))

	def __del__(self):
		self.Logger.debug("~Torchlight()")


class TorchlightHandler():
	def __init__(self, loop):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Loop = loop if loop else asyncio.get_event_loop()
		self._Client = None
		self.Torchlight = None
		self.Config = Config()

		asyncio.ensure_future(self._Connect(), loop = self.Loop)

	async def _Connect(self):
		# Connect to API
		self._Client = AsyncClient(self.Loop, self.Config["SMAPIServer"]["Host"], self.Config["SMAPIServer"]["Port"], self)
		await self._Client.Connect()

		self.Torchlight = Torchlight(self)

		# Pre Hook for late load
		await self.Torchlight.GameEvents._Register(["player_connect", "player_activate"])
		await self.Torchlight.Forwards._Register(["OnClientPostAdminCheck"])

		self.Torchlight.InitModules()

		# Late load
		await self.Torchlight.GameEvents.Replay(["player_connect", "player_activate"])
		await self.Torchlight.Forwards.Replay(["OnClientPostAdminCheck"])

	async def Send(self, data):
		return await self._Client.Send(data)

	def OnPublish(self, obj):
		self.Torchlight.OnPublish(obj)

	def OnDisconnect(self, exc):
		self.Logger.info("OnDisconnect({0})".format(exc))
		self.Torchlight = None

		asyncio.ensure_future(self._Connect(), loop = self.Loop)

	def __del__(self):
		self.Logger.debug("~TorchlightHandler()")
