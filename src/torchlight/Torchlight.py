#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import textwrap
import weakref
from typing import Any, Dict, Optional, Set

from AccessManager import AccessManager
from AsyncClient import AsyncClient
from AudioManager import AudioManager
from CommandHandler import CommandHandler
from Config import Config
from PlayerManager import Player, PlayerManager
from SourceModAPI import SourceModAPI
from Subscribe import Forwards, GameEvents
from Utils import Utils
from Colors import color

class Torchlight:
    def __init__(self, master: TorchlightHandler):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Master: TorchlightHandler = master
        self.Config = self.Master.Config
        self.WeakSelf = weakref.ref(self)

        self.API = SourceModAPI(self.WeakSelf)
        self.GameEvents = GameEvents(self.WeakSelf)
        self.Forwards = Forwards(self.WeakSelf)

        self.DisableVotes: Set = set()
        self.Disabled = 0
        self.LastUrl = None

    def InitModules(self) -> None:
        self.Access = AccessManager()
        self.Access.Load()

        self.Players = PlayerManager(self.WeakSelf)

        self.AudioManager = AudioManager(self.WeakSelf)

        self.CommandHandler = CommandHandler(self.WeakSelf)
        self.CommandHandler.Setup()

        self.GameEvents.HookEx("server_spawn", self.Event_ServerSpawn)
        self.GameEvents.HookEx("player_say", self.Event_PlayerSay)

    def SayChat(self, message: str, player: Optional[Player] = None) -> None:
        message = "{0}{1}[Torchlight]: {2}{3}".format(color.default, color.aqua, color.default, message)
        if len(message) > 976:
            message = message[:973] + "..."
        lines = textwrap.wrap(message, 244, break_long_words=True)
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

    def SayPrivate(self, player: Player, message: str) -> None:
        message = "{0}{1}[Torchlight]: {2}{3}".format(color.default, color.aqua, color.default, message)
        if len(message) > 976:
            message = message[:973] + "..."
        lines = textwrap.wrap(message, 244, break_long_words=True)
        for line in lines:
            asyncio.ensure_future(self.API.PrintToChat(player.Index, line))

    def Reload(self) -> None:
        self.Config.Load()
        self.CommandHandler.NeedsReload = True

    async def Send(self, data: Any) -> Optional[Any]:
        return await self.Master.Send(data)

    def OnPublish(self, obj: Dict[str, str]) -> None:
        if obj["module"] == "gameevents":
            self.GameEvents.OnPublish(obj)
        elif obj["module"] == "forwards":
            self.Forwards.OnPublish(obj)

    def Event_ServerSpawn(
        self,
        hostname: str,
        address: str,
        ip: str,
        port: str,
        game: str,
        mapname: str,
        maxplayers: str,
        os: str,
        dedicated: str,
        password: str,
    ) -> None:
        self.DisableVotes = set()
        self.Disabled = 0

    def Event_PlayerSay(self, userid: int, text: str) -> None:
        if userid == 0:
            return

        Player = self.Players.FindUserID(userid)
        asyncio.ensure_future(self.CommandHandler.HandleCommand(text, Player))

    def __del__(self) -> None:
        self.Logger.debug("~Torchlight()")


class TorchlightHandler:
    def __init__(self, loop: Optional[asyncio.AbstractEventLoop]):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Loop: asyncio.AbstractEventLoop = (
            loop if loop else asyncio.get_event_loop()
        )
        self._Client: Optional[AsyncClient] = None
        self.Torchlight: Optional[Torchlight] = None
        self.Config = Config()

        asyncio.ensure_future(self._Connect(), loop=self.Loop)

    async def _Connect(self) -> None:
        if not self.Config["SMAPIServer"]:
            raise Exception("Could not find SMAPIServer field in config")

        # Connect to API
        self._Client = AsyncClient(
            self.Loop,
            self.Config["SMAPIServer"]["Host"],
            self.Config["SMAPIServer"]["Port"],
            self,
        )
        await self._Client.Connect()

        self.Torchlight = Torchlight(self)

        # Pre Hook for late load
        await self.Torchlight.GameEvents._Register(
            ["player_connect", "player_activate"]
        )
        await self.Torchlight.Forwards._Register(["OnClientPostAdminCheck"])

        self.Torchlight.InitModules()

        # Late load
        await self.Torchlight.GameEvents.Replay(["player_connect", "player_activate"])
        await self.Torchlight.Forwards.Replay(["OnClientPostAdminCheck"])

    async def Send(self, data: Any) -> Optional[Any]:
        if self._Client:
            return await self._Client.Send(data)
        return None

    def OnPublish(self, obj: Dict[str, str]) -> None:
        if self.Torchlight:
            self.Torchlight.OnPublish(obj)

    def OnDisconnect(self, exc: Optional[Exception]) -> None:
        self.Logger.info("OnDisconnect({0})".format(exc))
        self.Torchlight = None

        asyncio.ensure_future(self._Connect(), loop=self.Loop)

    def __del__(self) -> None:
        self.Logger.debug("~TorchlightHandler()")
