#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
from .Constants import *

class PlayerManager():
	def __init__(self, master):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Torchlight = master

		self.Players = [None] * (MAXPLAYERS + 1)
		self.Storage = self.StorageManager(self)

		self.Torchlight().GameEvents.HookEx("player_connect", self.Event_PlayerConnect)
		self.Torchlight().GameEvents.HookEx("player_activate", self.Event_PlayerActivate)
		self.Torchlight().Forwards.HookEx("OnClientPostAdminCheck", self.OnClientPostAdminCheck)
		self.Torchlight().GameEvents.HookEx("player_info", self.Event_PlayerInfo)
		self.Torchlight().GameEvents.HookEx("player_disconnect", self.Event_PlayerDisconnect)
		self.Torchlight().GameEvents.HookEx("server_spawn", self.Event_ServerSpawn)

	def Event_PlayerConnect(self, name, index, userid, networkid, address, bot):
		index += 1
		self.Logger.info("OnConnect(name={0}, index={1}, userid={2}, networkid={3}, address={4}, bot={5})"
			.format(name, index, userid, networkid, address, bot))
		if self.Players[index] != None:
			self.Logger.error("!!! Player already exists, overwriting !!!")

		self.Players[index] = self.Player(self, index, userid, networkid, address, name)
		self.Players[index].OnConnect()

	def Event_PlayerActivate(self, userid):
		self.Logger.info("Pre_OnActivate(userid={0})".format(userid))
		index = self.FindUserID(userid).Index
		self.Logger.info("OnActivate(index={0}, userid={1})".format(index, userid))

		self.Players[index].OnActivate()

	def OnClientPostAdminCheck(self, client):
		self.Logger.info("OnClientPostAdminCheck(client={0})".format(client))

		asyncio.ensure_future(self.Players[client].OnClientPostAdminCheck())

	def Event_PlayerInfo(self, name, index, userid, networkid, bot):
		index += 1
		self.Logger.info("OnInfo(name={0}, index={1}, userid={2}, networkid={3}, bot={4})"
			.format(name, index, userid, networkid, bot))

		# We've connected to the server and receive info events about the already connected players
		# Emulate connect message
		if not self.Players[index]:
			self.Event_PlayerConnect(name, index - 1, userid, networkid, bot)
		else:
			self.Players[index].OnInfo(name)

	def Event_PlayerDisconnect(self, userid, reason, name, networkid, bot):
		index = self.FindUserID(userid).Index
		self.Logger.info("OnDisconnect(index={0}, userid={1}, reason={2}, name={3}, networkid={4}, bot={5})"
			.format(index, userid, reason, name, networkid, bot))

		self.Players[index].OnDisconnect(reason)
		self.Players[index] = None

	def Event_ServerSpawn(self, hostname, address, ip, port, game, mapname, maxplayers, os, dedicated, password):
		self.Logger.info("ServerSpawn(mapname={0})"
			.format(mapname))

		self.Storage.Reset()

		for i in range(1, len(self.Players)):
			if self.Players[i]:
				self.Players[i].OnDisconnect("mapchange")
				self.Players[i].OnConnect()

	def FindUniqueID(self, uniqueid):
		for Player in self.Players:
			if Player and Player.UniqueID == uniqueid:
				return Player

	def FindUserID(self, userid):
		for Player in self.Players:
			if Player and Player.UserID == userid:
				return Player

	def FindName(self, name):
		for Player in self.Players:
			if Player and Player.Name == name:
				return Player

	def __len__(self):
		Count = 0
		for i in range(1, len(self.Players)):
			if self.Players[i]:
				Count += 1
		return Count

	def __setitem__(self, key, value):
		if key > 0 and key <= MAXPLAYERS:
			self.Players[key] = value

	def __getitem__(self, key):
		if key > 0 and key <= MAXPLAYERS:
			return self.Players[key]

	def __iter__(self):
		for i in range(1, len(self.Players)):
			if self.Players[i]:
				yield self.Players[i]

	class StorageManager():
		def __init__(self, master):
			self.PlayerManager = master
			self.Storage = dict()

		def Reset(self):
			self.Storage = dict()

		def __getitem__(self, key):
			if not key in self.Storage:
				self.Storage[key] = dict()

			return self.Storage[key]

	class Admin():
		def __init__(self):
			self._FlagBits = 0

		def FlagBits(self):
			return self._FlagBits

		def Reservation(self): return (self._FlagBits & ADMFLAG_RESERVATION)
		def Generic(self): return (self._FlagBits & ADMFLAG_GENERIC)
		def Kick(self): return (self._FlagBits & ADMFLAG_KICK)
		def Ban(self): return (self._FlagBits & ADMFLAG_BAN)
		def Unban(self): return (self._FlagBits & ADMFLAG_UNBAN)
		def Slay(self): return (self._FlagBits & ADMFLAG_SLAY)
		def Changemap(self): return (self._FlagBits & ADMFLAG_CHANGEMAP)
		def Convars(self): return (self._FlagBits & ADMFLAG_CONVARS)
		def Config(self): return (self._FlagBits & ADMFLAG_CONFIG)
		def Chat(self): return (self._FlagBits & ADMFLAG_CHAT)
		def Vote(self): return (self._FlagBits & ADMFLAG_VOTE)
		def Password(self): return (self._FlagBits & ADMFLAG_PASSWORD)
		def RCON(self): return (self._FlagBits & ADMFLAG_RCON)
		def Cheats(self): return (self._FlagBits & ADMFLAG_CHEATS)
		def Root(self): return (self._FlagBits & ADMFLAG_ROOT)
		def Custom1(self): return (self._FlagBits & ADMFLAG_CUSTOM1)
		def Custom2(self): return (self._FlagBits & ADMFLAG_CUSTOM2)
		def Custom3(self): return (self._FlagBits & ADMFLAG_CUSTOM3)
		def Custom4(self): return (self._FlagBits & ADMFLAG_CUSTOM4)
		def Custom5(self): return (self._FlagBits & ADMFLAG_CUSTOM5)
		def Custom6(self): return (self._FlagBits & ADMFLAG_CUSTOM6)

	class Player():
		def __init__(self, master, index, userid, uniqueid, address, name):
			self.PlayerManager = master
			self.Torchlight = self.PlayerManager.Torchlight
			self.Index = index
			self.UserID = userid
			self.UniqueID = uniqueid
			self.Address = address
			self.Name = name
			self.Access = None
			self.Admin = self.PlayerManager.Admin()
			self.Storage = None
			self.Active = False
			self.ChatCooldown = 0

		def OnConnect(self):
			self.Storage = self.PlayerManager.Storage[self.UniqueID]

			if not "Audio" in self.Storage:
				self.Storage["Audio"] = dict({"Uses": 0, "LastUse": 0.0, "LastUseLength": 0.0, "TimeUsed": 0.0})

			self.Access = self.Torchlight().Access[self.UniqueID]

		def OnActivate(self):
			self.Active = True

		async def OnClientPostAdminCheck(self):
			self.Admin._FlagBits = (await self.Torchlight().API.GetUserFlagBits(self.Index))["result"]
			self.PlayerManager.Logger.info("#{0} \"{1}\"({2}) FlagBits: {3}".format(self.UserID, self.Name, self.UniqueID, self.Admin._FlagBits))
			if not self.Access:
				if self.Admin.RCON():
					self.Access = dict({"level": 6, "name": "SAdmin"})
				elif self.Admin.Generic():
					self.Access = dict({"level": 3, "name": "Admin"})
				elif self.Admin.Custom1():
					self.Access = dict({"level": 1, "name": "VIP"})

			if self.PlayerManager.Torchlight().Config["DefaultLevel"]:
				if self.Access and self.Access["level"] < self.PlayerManager.Torchlight().Config["DefaultLevel"]:
					self.Access = dict({"level": self.PlayerManager.Torchlight().Config["DefaultLevel"], "name": "Default"})

		def OnInfo(self, name):
			self.Name = name

		def OnDisconnect(self, message):
			self.Active = False
			self.Storage = None
			self.Torchlight().AudioManager.OnDisconnect(self)
