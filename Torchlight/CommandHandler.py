#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import sys
import re
import traceback
import math
from importlib import reload
from . import Commands

class CommandHandler():
	def __init__(self, Torchlight):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Torchlight = Torchlight
		self.Commands = []
		self.NeedsReload = False

	def Setup(self):
		Counter = len(self.Commands)
		self.Commands.clear()
		if Counter:
			self.Logger.info(sys._getframe().f_code.co_name + " Unloaded {0} commands!".format(Counter))

		Counter = 0
		for subklass in sorted(Commands.BaseCommand.__subclasses__(), key = lambda x: x.Order, reverse = True):
			try:
				Command = subklass(self.Torchlight)
				if hasattr(Command, "_setup"):
					Command._setup()
			except Exception as e:
				self.Logger.error(traceback.format_exc())
			else:
				self.Commands.append(Command)
				Counter += 1

		self.Logger.info(sys._getframe().f_code.co_name + " Loaded {0} commands!".format(Counter))

	def Reload(self):
		try:
			reload(Commands)
		except Exception as e:
			self.Logger.error(traceback.format_exc())
		else:
			self.Setup()

	async def HandleCommand(self, line, player):
		Message = line.split(sep = ' ', maxsplit = 1)
		if len(Message) < 2:
			Message.append("")
		Message[1] = Message[1].strip()

		if Message[1] and self.Torchlight().LastUrl:
			Message[1] = Message[1].replace("!last", self.Torchlight().LastUrl)
			line = Message[0] + ' ' + Message[1]

		Level = 0
		if player.Access:
			Level = player.Access["level"]

		RetMessage = None
		Ret = None
		for Command in self.Commands:
			for Trigger in Command.Triggers:
				Match = False
				RMatch = None
				if isinstance(Trigger, tuple):
					if Message[0].lower().startswith(Trigger[0], 0, Trigger[1]):
						Match = True
				elif isinstance(Trigger, str):
					if Message[0].lower() == Trigger.lower():
						Match = True
				else: # compiled regex
					RMatch = Trigger.search(line)
					if RMatch:
						Match = True

				if not Match:
					continue

				self.Logger.debug(sys._getframe().f_code.co_name + " \"{0}\" Match -> {1} | {2}".format(player.Name, Command.__class__.__name__, Trigger))

				if Level < Command.Level:
					RetMessage = "You do not have access to this command! (You: {0} | Required: {1})".format(Level, Command.Level)
					continue

				try:
					if RMatch:
						Ret = await Command._rfunc(line, RMatch, player)
					else:
						Ret = await Command._func(Message, player)
				except Exception as e:
					self.Logger.error(traceback.format_exc())
					self.Torchlight().SayChat("Error: {0}".format(str(e)))

				RetMessage = None

				if isinstance(Ret, str):
					Message = Ret.split(sep = ' ', maxsplit = 1)
					Ret = None

				if Ret != None and Ret > 0:
					break

			if Ret != None and Ret >= 0:
				break

		if RetMessage:
			self.Torchlight().SayPrivate(player, RetMessage)

		if self.NeedsReload:
			self.NeedsReload = False
			self.Reload()

		return Ret
