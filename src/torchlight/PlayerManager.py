import asyncio
import logging
from typing import Generator, List, Optional

from torchlight.AccessManager import AccessManager
from torchlight.AudioManager import AudioManager
from torchlight.Constants import Clients
from torchlight.Player import Player
from torchlight.StorageManager import StorageManager
from torchlight.Torchlight import Torchlight


class PlayerManager:
    def __init__(
        self,
        torchlight: Torchlight,
        audio_manager: AudioManager,
        access_manager: AccessManager,
    ) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.audio_manager = audio_manager
        self.access_manager = access_manager

        self.players: List[Optional[Player]] = [None] * (Clients.MAXPLAYERS + 1)
        self.storage_manager = StorageManager()

    def Setup(self) -> None:
        self.torchlight.game_events.HookEx("player_connect", self.Event_PlayerConnect)
        self.torchlight.game_events.HookEx("player_activate", self.Event_PlayerActivate)
        self.torchlight.forwards.HookEx(
            "OnClientPostAdminCheck", self.OnClientPostAdminCheck
        )
        self.torchlight.game_events.HookEx("player_info", self.Event_PlayerInfo)
        self.torchlight.game_events.HookEx(
            "player_disconnect", self.Event_PlayerDisconnect
        )
        self.torchlight.game_events.HookEx("server_spawn", self.Event_ServerSpawn)

    def Event_PlayerConnect(
        self, name: str, index: int, userid: int, networkid: str, address: str, bot: int
    ) -> None:
        index += 1
        self.Logger.info(
            "OnConnect(name={0}, index={1}, userid={2}, networkid={3}, address={4}, bot={5})".format(
                name, index, userid, networkid, address, bot
            )
        )

        player = self.players[index]

        if player is not None:
            self.Logger.error("!!! Player already exists, overwriting !!!")

        player = Player(index, userid, networkid, address, name)

        self.players[index] = player
        access = self.access_manager.get_access(player)
        player.OnConnect(self.storage_manager[player.UniqueID], access)

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

        player = self.players[client]
        if player is None:
            return

        asyncio.ensure_future(self.OnClientPostAdminCheckAsync(player))

    async def OnClientPostAdminCheckAsync(self, player: Player) -> None:
        flag_bits: int = (await self.torchlight.API.GetUserFlagBits(player.Index))[
            "result"
        ]
        player.OnClientPostAdminCheck(flag_bits, self.torchlight.config)

    def Event_PlayerInfo(
        self, name: str, index: int, userid: int, networkid: str, bot: int
    ) -> None:
        index += 1
        self.Logger.info(
            "OnInfo(name={0}, index={1}, userid={2}, networkid={3}, bot={4})".format(
                name, index, userid, networkid, bot
            )
        )
        player = self.players[index]

        # We've connected to the server and receive info events about the already connected players
        # Emulate connect message
        if player is None:
            self.Event_PlayerConnect(name, index - 1, userid, networkid, "", bot)
        else:
            player.OnInfo(name)

    def Event_PlayerDisconnect(
        self, userid: int, reason: str, name: str, networkid: str, bot: int
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
        self.audio_manager.OnDisconnect(player)
        self.players[player.Index] = None

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

        self.storage_manager.Reset()

        for i in range(1, len(self.players)):
            player = self.players[i]
            if player is not None:
                access = self.access_manager.get_access(player)
                player.OnDisconnect("mapchange")
                player.OnConnect(
                    self.storage_manager[player.UniqueID],
                    access,
                )

    def FindUniqueID(self, uniqueid: int) -> Optional[Player]:
        for player in self.players:
            if player and player.UniqueID == uniqueid:
                return player
        return None

    def FindUserID(self, userid: int) -> Optional[Player]:
        for player in self.players:
            if player and player.UserID == userid:
                return player
        return None

    def FindName(self, name: str) -> Optional[Player]:
        for player in self.players:
            if player and player.Name == name:
                return player
        return None

    def __len__(self) -> int:
        Count = 0
        for i in range(1, len(self.players)):
            if self.players[i]:
                Count += 1
        return Count

    def __setitem__(self, key: int, value: Optional[Player]) -> None:
        if key > 0 and key <= Clients.MAXPLAYERS:
            self.players[key] = value

    def __getitem__(self, key: int) -> Optional[Player]:
        if key > 0 and key <= Clients.MAXPLAYERS:
            return self.players[key]
        return None

    def __iter__(self) -> Generator[Player, None, None]:
        for i in range(1, len(self.players)):
            player = self.players[i]
            if player is not None:
                yield player
