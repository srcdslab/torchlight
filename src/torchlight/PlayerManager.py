#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Any, Dict, Generator, List, Optional

from Torchlight import Torchlight

from .Constants import *


class StorageManager:
    def __init__(self, master: PlayerManager):
        self.PlayerManager: PlayerManager = master
        self.Storage: Dict = dict()

    def Reset(self) -> None:
        self.Storage = dict()

    def __getitem__(self, key: int) -> Dict:
        if not key in self.Storage:
            self.Storage[key] = dict()

        return self.Storage[key]


class Admin:
    def __init__(self) -> None:
        self._FlagBits = 0

    def FlagBits(self) -> int:
        return self._FlagBits

    def Reservation(self) -> int:
        return self._FlagBits & ADMFLAG_RESERVATION

    def Generic(self) -> int:
        return self._FlagBits & ADMFLAG_GENERIC

    def Kick(self) -> int:
        return self._FlagBits & ADMFLAG_KICK

    def Ban(self) -> int:
        return self._FlagBits & ADMFLAG_BAN

    def Unban(self) -> int:
        return self._FlagBits & ADMFLAG_UNBAN

    def Slay(self) -> int:
        return self._FlagBits & ADMFLAG_SLAY

    def Changemap(self) -> int:
        return self._FlagBits & ADMFLAG_CHANGEMAP

    def Convars(self) -> int:
        return self._FlagBits & ADMFLAG_CONVARS

    def Config(self) -> int:
        return self._FlagBits & ADMFLAG_CONFIG

    def Chat(self) -> int:
        return self._FlagBits & ADMFLAG_CHAT

    def Vote(self) -> int:
        return self._FlagBits & ADMFLAG_VOTE

    def Password(self) -> int:
        return self._FlagBits & ADMFLAG_PASSWORD

    def RCON(self) -> int:
        return self._FlagBits & ADMFLAG_RCON

    def Cheats(self) -> int:
        return self._FlagBits & ADMFLAG_CHEATS

    def Root(self) -> int:
        return self._FlagBits & ADMFLAG_ROOT

    def Custom1(self) -> int:
        return self._FlagBits & ADMFLAG_CUSTOM1

    def Custom2(self) -> int:
        return self._FlagBits & ADMFLAG_CUSTOM2

    def Custom3(self) -> int:
        return self._FlagBits & ADMFLAG_CUSTOM3

    def Custom4(self) -> int:
        return self._FlagBits & ADMFLAG_CUSTOM4

    def Custom5(self) -> int:
        return self._FlagBits & ADMFLAG_CUSTOM5

    def Custom6(self) -> int:
        return self._FlagBits & ADMFLAG_CUSTOM6


class Player:
    def __init__(
        self,
        master: PlayerManager,
        index: int,
        userid: int,
        uniqueid: int,
        address: str,
        name: str,
    ):
        self.player_manager: PlayerManager = master
        self.Torchlight = self.player_manager.Torchlight
        self.Index = index
        self.UserID = userid
        self.UniqueID = uniqueid
        self.Address = address
        self.Name = name
        self.Access: Optional[Dict[str, Any]] = None
        self.Admin = Admin()
        self.Storage: Dict = dict()
        self.Active = False
        self.ChatCooldown = 0

    def OnConnect(self) -> None:
        self.Storage = self.player_manager.Storage[self.UniqueID]

        if not "Audio" in self.Storage:
            self.Storage["Audio"] = dict(
                {"Uses": 0, "LastUse": 0.0, "LastUseLength": 0.0, "TimeUsed": 0.0}
            )

        self.Access = self.Torchlight().Access[self.UniqueID]

    def OnActivate(self) -> None:
        self.Active = True

    async def OnClientPostAdminCheck(self) -> None:
        self.Admin._FlagBits = (
            await self.Torchlight().API.GetUserFlagBits(self.Index)
        )["result"]
        self.player_manager.Logger.info(
            "#{0} \"{1}\"({2}) FlagBits: {3}".format(
                self.UserID, self.Name, self.UniqueID, self.Admin._FlagBits
            )
        )
        if not self.Access:
            if self.Admin.RCON() or self.Admin.Root():
                self.Access = dict(
                    {
                        "level": self.Torchlight().Config["AccessLevel"]["Root"],
                        "name": "SAdmin",
                    }
                )
            elif self.Admin.Ban():
                self.Access = dict(
                    {
                        "level": self.Torchlight().Config["AccessLevel"]["Admin"],
                        "name": "Admin",
                    }
                )
            elif self.Admin.Generic():
                self.Access = dict(
                    {
                        "level": self.Torchlight().Config["AccessLevel"][
                            "DonatedAdmin"
                        ],
                        "name": "DAdmin",
                    }
                )
            elif self.Admin.Custom1():
                self.Access = dict(
                    {
                        "level": self.Torchlight().Config["AccessLevel"]["VIP"],
                        "name": "VIP",
                    }
                )

        if self.player_manager.Torchlight().Config["DefaultLevel"]:
            if (
                self.Access
                and self.Access["level"]
                < self.player_manager.Torchlight().Config["DefaultLevel"]
            ):
                self.Access = dict(
                    {
                        "level": self.player_manager.Torchlight().Config[
                            "DefaultLevel"
                        ],
                        "name": "Default",
                    }
                )

    def OnInfo(self, name: str) -> None:
        self.Name = name

    def OnDisconnect(self, message: str) -> None:
        self.Active = False
        self.Storage = dict()
        self.Torchlight().AudioManager.OnDisconnect(self)


class PlayerManager:
    def __init__(self, master: Torchlight):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Torchlight: Torchlight = master

        self.Players: List[Optional[Player]] = [None] * (MAXPLAYERS + 1)
        self.Storage = StorageManager(self)

        self.Torchlight().GameEvents.HookEx("player_connect", self.Event_PlayerConnect)
        self.Torchlight().GameEvents.HookEx(
            "player_activate", self.Event_PlayerActivate
        )
        self.Torchlight().Forwards.HookEx(
            "OnClientPostAdminCheck", self.OnClientPostAdminCheck
        )
        self.Torchlight().GameEvents.HookEx("player_info", self.Event_PlayerInfo)
        self.Torchlight().GameEvents.HookEx(
            "player_disconnect", self.Event_PlayerDisconnect
        )
        self.Torchlight().GameEvents.HookEx("server_spawn", self.Event_ServerSpawn)

    def Event_PlayerConnect(
        self, name: str, index: int, userid: int, networkid: int, address: str, bot: int
    ) -> None:
        index += 1
        self.Logger.info(
            "OnConnect(name={0}, index={1}, userid={2}, networkid={3}, address={4}, bot={5})".format(
                name, index, userid, networkid, address, bot
            )
        )

        player = self.Players[index]

        if player is not None:
            self.Logger.error("!!! Player already exists, overwriting !!!")

        player = Player(self, index, userid, networkid, address, name)

        self.Players[index] = player
        player.OnConnect()

    def Event_PlayerActivate(self, userid: int) -> None:
        self.Logger.info("Pre_OnActivate(userid={0})".format(userid))

        player = self.FindUserID(userid)
        if player is None:
            return

        self.Logger.info(
            "OnActivate(index={0}, userid={1})".format(player.Index, userid)
        )

        player.OnActivate()

    def OnClientPostAdminCheck(self, client: int) -> None:
        self.Logger.info("OnClientPostAdminCheck(client={0})".format(client))

        player = self.Players[client]
        if player is None:
            return

        asyncio.ensure_future(player.OnClientPostAdminCheck())

    def Event_PlayerInfo(
        self, name: str, index: int, userid: int, networkid: int, bot: int
    ) -> None:
        index += 1
        self.Logger.info(
            "OnInfo(name={0}, index={1}, userid={2}, networkid={3}, bot={4})".format(
                name, index, userid, networkid, bot
            )
        )
        player = self.Players[index]

        # We've connected to the server and receive info events about the already connected players
        # Emulate connect message
        if player is None:
            self.Event_PlayerConnect(name, index - 1, userid, networkid, "", bot)
        else:
            player.OnInfo(name)

    def Event_PlayerDisconnect(
        self, userid: int, reason: str, name: str, networkid: int, bot: int
    ) -> None:
        player = self.FindUserID(userid)
        if player is None:
            return

        self.Logger.info(
            "OnDisconnect(index={0}, userid={1}, reason={2}, name={3}, networkid={4}, bot={5})".format(
                player.Index, userid, reason, name, networkid, bot
            )
        )

        player.OnDisconnect(reason)
        self.Players[player.Index] = None

    def Event_ServerSpawn(
        self,
        hostname: str,
        address: str,
        ip: str,
        port: int,
        game: str,
        mapname: str,
        maxplayers: int,
        os: str,
        dedicated: str,
        password: str,
    ) -> None:
        self.Logger.info("ServerSpawn(mapname={0})".format(mapname))

        self.Storage.Reset()

        for i in range(1, len(self.Players)):
            player = self.Players[i]
            if player is not None:
                player.OnDisconnect("mapchange")
                player.OnConnect()

    def FindUniqueID(self, uniqueid: int) -> Optional[Player]:
        for Player in self.Players:
            if Player and Player.UniqueID == uniqueid:
                return Player
        return None

    def FindUserID(self, userid: int) -> Optional[Player]:
        for Player in self.Players:
            if Player and Player.UserID == userid:
                return Player
        return None

    def FindName(self, name: str) -> Optional[Player]:
        for Player in self.Players:
            if Player and Player.Name == name:
                return Player
        return None

    def __len__(self) -> int:
        Count = 0
        for i in range(1, len(self.Players)):
            if self.Players[i]:
                Count += 1
        return Count

    def __setitem__(self, key: int, value: Optional[Player]) -> None:
        if key > 0 and key <= MAXPLAYERS:
            self.Players[key] = value

    def __getitem__(self, key: int) -> Optional[Player]:
        if key > 0 and key <= MAXPLAYERS:
            return self.Players[key]
        return None

    def __iter__(self) -> Generator[Player, None, None]:
        for i in range(1, len(self.Players)):
            player = self.Players[i]
            if player is not None:
                yield player
