import asyncio
import logging

from torchlight.AccessManager import AccessManager
from torchlight.AudioManager import AudioManager
from torchlight.Constants import Clients
from torchlight.Player import Player
from torchlight.Sourcemod import SourcemodConfig
from torchlight.Torchlight import Torchlight


class PlayerManager:
    def __init__(
        self,
        torchlight: Torchlight,
        audio_manager: AudioManager,
        access_manager: AccessManager,
        sourcemod_config: SourcemodConfig,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.audio_manager = audio_manager
        self.access_manager = access_manager
        self.sourcemod_config = sourcemod_config
        self.audio_storage: dict[str, dict] = {}

        self.players: list[Player | None] = [None] * (Clients.MAXPLAYERS + 1)
        self.player_count: int = 0

    def Setup(self) -> None:
        self.torchlight.game_events.HookEx(
            "player_connect", self.Event_PlayerConnect
        )
        self.torchlight.game_events.HookEx(
            "player_activate", self.Event_PlayerActivate
        )
        self.torchlight.forwards.HookEx(
            "OnClientPostAdminCheck", self.OnClientPostAdminCheck
        )
        self.torchlight.game_events.HookEx("player_info", self.Event_PlayerInfo)
        self.torchlight.game_events.HookEx(
            "player_disconnect", self.Event_PlayerDisconnect
        )
        self.torchlight.game_events.HookEx(
            "server_spawn", self.Event_ServerSpawn
        )

    def Event_PlayerConnect(
        self,
        name: str,
        index: int,
        userid: int,
        networkid: str,
        address: str,
        bot: int,
    ) -> None:
        self.player_count += 1
        index += 1
        self.logger.info(
            "OnConnect(name={}, index={}, userid={}, networkid={}, address={}, bot={})".format(
                name, index, userid, networkid, address, bot
            )
        )

        player = self.players[index]

        if player is not None:
            self.logger.error("!!! Player already exists, overwriting !!!")

        player = Player(index, userid, networkid, address, name)

        admin_override = self.access_manager.get_admin(
            unique_id=player.unique_id
        )
        if admin_override is not None:
            player.admin = admin_override

        for unique_id, audio_stored in self.audio_storage.items():
            if player.unique_id == unique_id:
                player.storage = audio_stored
                break

        self.audio_storage[player.unique_id] = player.storage
        self.players[index] = player

        player.OnConnect()

    def Event_PlayerActivate(self, userid: int) -> None:
        self.logger.info(f"Pre_OnActivate(userid={userid})")

        player = self.FindUserID(userid)
        if player is None:
            return

        self.logger.info(f"OnActivate(index={player.index}, userid={userid})")

        player.OnActivate()

    def OnClientPostAdminCheck(self, client: int) -> None:
        self.logger.info(f"OnClientPostAdminCheck(client={client})")

        player = self.players[client]
        if player is None:
            return

        asyncio.ensure_future(self.OnClientPostAdminCheckAsync(player))

    async def OnClientPostAdminCheckAsync(self, player: Player) -> None:
        flag_bits: int = (
            await self.torchlight.sourcemod_api.GetUserFlagBits(player.index)
        )["result"]
        player.OnClientPostAdminCheck(
            flag_bits=flag_bits, sourcemod_config=self.sourcemod_config
        )

    def Event_PlayerInfo(
        self, name: str, index: int, userid: int, networkid: str, bot: int
    ) -> None:
        index += 1
        self.logger.info(
            "OnInfo(name={}, index={}, userid={}, networkid={}, bot={})".format(
                name, index, userid, networkid, bot
            )
        )
        player = self.players[index]

        # We've connected to the server and receive info events about the already connected players
        # Emulate connect message
        if player is None:
            self.Event_PlayerConnect(
                name, index - 1, userid, networkid, "", bot
            )
        else:
            player.OnInfo(name)

    def Event_PlayerDisconnect(
        self, userid: int, reason: str, name: str, networkid: str, bot: int
    ) -> None:
        self.player_count -= 1

        player = self.FindUserID(userid)
        if player is None:
            return

        self.logger.info(
            "OnDisconnect(index={}, userid={}, reason={}, name={}, networkid={}, bot={})".format(
                player.index, userid, reason, name, networkid, bot
            )
        )

        self.audio_storage[player.unique_id] = player.storage
        player.OnDisconnect(reason)
        self.audio_manager.OnDisconnect(player)
        self.players[player.index] = None

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
        self.logger.info(f"ServerSpawn(mapname={mapname})")

        self.player_count = 0
        self.audio_storage = {}
        self.access_manager.Load()

        for i in range(1, Clients.MAXPLAYERS):
            player = self.players[i]
            if player is not None:
                self.player_count += 1
                if self.audio_manager.anti_spam.config["StopOnMapChange"]:
                    self.audio_manager.OnDisconnect(player)
                player.OnDisconnect("mapchange")
                admin_override = self.access_manager.get_admin(
                    unique_id=player.unique_id
                )
                if admin_override is not None:
                    player.admin = admin_override
                player.OnConnect()
                self.audio_storage[player.unique_id] = player.storage

    def FindUniqueID(self, uniqueid: str) -> Player | None:
        for player in self.players:
            if player and player.unique_id == uniqueid:
                return player
        return None

    def FindUserID(self, userid: int) -> Player | None:
        for player in self.players:
            if player and player.user_id == userid:
                return player
        return None

    def FindName(self, name: str) -> Player | None:
        for player in self.players:
            if player and player.name == name:
                return player
        return None
