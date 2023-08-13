import asyncio
import logging

from torchlight.AccessManager import AccessManager
from torchlight.AsyncClient import AsyncClient
from torchlight.AudioManager import AudioManager
from torchlight.CommandHandler import CommandHandler
from torchlight.Config import Config
from torchlight.PlayerManager import PlayerManager
from torchlight.Torchlight import Torchlight


class TorchlightHandler:
    def __init__(self, loop: asyncio.AbstractEventLoop | None, config: Config):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.loop: asyncio.AbstractEventLoop = (
            loop if loop else asyncio.get_event_loop()
        )

        self.Init()

        asyncio.ensure_future(self._Connect(), loop=self.loop)

    async def _Connect(self) -> None:
        # Connect to API
        await self.async_client.Connect()

        # Pre Hook for late load
        await self.torchlight.game_events._Register(
            ["player_connect", "player_activate"]
        )
        await self.torchlight.forwards._Register(["OnClientPostAdminCheck"])

        self.InitModules()

        # Late load
        await self.torchlight.game_events.Replay(
            ["player_connect", "player_activate"]
        )
        await self.torchlight.forwards.Replay(["OnClientPostAdminCheck"])

    def Init(self) -> None:
        self.async_client = AsyncClient(
            self.loop,
            self.config["SMAPIServer"],
        )
        self.async_client.AddCallback("OnPublish", self.OnPublish)
        self.async_client.AddCallback("OnDisconnect", self.OnDisconnect)

        self.torchlight = Torchlight(self.config, self.loop, self.async_client)
        self.torchlight.AddCallback("OnReload", self.OnReload)

        self.access_manager = AccessManager(self.config.config_folder)

        self.audio_manager = AudioManager(self.torchlight)

        self.player_manager = PlayerManager(
            self.torchlight, self.audio_manager, self.access_manager
        )

        self.command_handler = CommandHandler(
            self.torchlight,
            self.access_manager,
            self.player_manager,
            self.audio_manager,
        )

    def InitModules(self) -> None:
        self.access_manager.Load()

        self.player_manager.Setup()

        self.command_handler.Setup()

        self.torchlight.game_events.HookEx(
            "server_spawn", self.Event_ServerSpawn
        )
        self.torchlight.game_events.HookEx("player_say", self.Event_PlayerSay)

    def OnReload(self) -> None:
        self.command_handler.needs_reload = True

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
        self.torchlight.disable_votes = set()
        self.torchlight.disabled = 0

    def Event_PlayerSay(self, userid: int, text: str) -> None:
        if userid == 0:
            return

        player = self.player_manager.FindUserID(userid)
        if player is None:
            return

        asyncio.ensure_future(self.command_handler.HandleCommand(text, player))

    def OnPublish(self, obj: dict[str, str]) -> None:
        self.torchlight.OnPublish(obj)

    def OnDisconnect(self, exc: Exception | None) -> None:
        self.logger.info(f"OnDisconnect({exc})")

        self.Init()

        asyncio.ensure_future(self._Connect(), loop=self.loop)

    def __del__(self) -> None:
        self.logger.debug("~TorchlightHandler()")
