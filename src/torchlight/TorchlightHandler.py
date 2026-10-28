import asyncio
import logging
import sys
import traceback

from torchlight.AccessManager import AccessManager
from torchlight.AsyncClient import AsyncClient
from torchlight.AudioManager import AudioManager
from torchlight.CommandHandler import CommandHandler
from torchlight.Config import Config
from torchlight.PlayerManager import PlayerManager
from torchlight.Sourcemod import SourcemodConfig
from torchlight.Torchlight import Torchlight
from torchlight.TriggerManager import TriggerManager
from torchlight.Utils import Utils


class TorchlightHandler:
    def __init__(self, loop: asyncio.AbstractEventLoop | None, config: Config):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.loop: asyncio.AbstractEventLoop = loop if loop else asyncio.get_event_loop()

        # Bumped on every (re)connect and on shutdown: a _Connect() that outlived its link
        # sees a newer generation and bails out instead of initializing the next graph.
        self.connection_generation = 0
        self.connect_task: asyncio.Task | None = None
        self.shutting_down = False

        self.Init()

        self._StartConnect()

    def _StartConnect(self) -> None:
        self.connection_generation += 1
        self.connect_task = Utils.FireAndForget(self._Connect(self.connection_generation), self.logger)

    def _CancelConnect(self) -> None:
        if self.connect_task is not None and not self.connect_task.done():
            self.connect_task.cancel()
        self.connect_task = None

    async def _Connect(self, generation: int) -> None:
        # Bind this generation's objects: OnDisconnect() rebinds self.* to a new graph.
        async_client = self.async_client
        torchlight = self.torchlight

        # Connect to API
        await async_client.Connect()

        # Pre Hook for late load
        await torchlight.game_events._Register(["player_connect", "player_activate"])
        await torchlight.forwards._Register(["OnClientPostAdminCheck", "OnMenuSelect"])

        if generation != self.connection_generation:
            # The link dropped while registering: OnDisconnect() already built a new graph
            # and started its own _Connect(), which must be the only one to set it up.
            self.logger.info(f"Connection #{generation} superseded during setup, aborting")
            return

        self.InitModules()

        # Late load
        await torchlight.game_events.Replay(["player_connect", "player_activate"])
        if generation != self.connection_generation:
            return
        await torchlight.forwards.Replay(["OnClientPostAdminCheck"])

    def Init(self) -> None:
        # Init() also runs on reconnect; OnDisconnect() tears the previous graph down.
        self.access_manager = AccessManager(self.config.config_folder)
        self.access_manager.Load()

        self.trigger_manager = TriggerManager(config_folder=self.config.config_folder, config=self.config)
        self.trigger_manager.Load()

        self.sourcemod_config = SourcemodConfig(config_folder=self.config.config_folder, config=self.config)
        self.sourcemod_config.Load()

        self.async_client = AsyncClient(
            self.loop,
            self.config["SMAPIServer"],
        )
        self.async_client.AddCallback("OnPublish", self.OnPublish)
        self.async_client.AddCallback("OnDisconnect", self.OnDisconnect)

        self.torchlight = Torchlight(self.config, self.loop, self.async_client)
        self.torchlight.AddCallback("OnReload", self.OnReload)

        self.audio_manager = AudioManager(self.torchlight)

        self.player_manager = PlayerManager(
            self.torchlight,
            self.audio_manager,
            self.access_manager,
            self.sourcemod_config,
        )

        self.command_handler = CommandHandler(
            self.torchlight,
            self.access_manager,
            self.player_manager,
            self.audio_manager,
            self.trigger_manager,
        )

        self.player_manager.torchlight.command_handler = self.command_handler

    def InitModules(self) -> None:
        self.player_manager.Setup()

        self.command_handler.Setup()

        self.torchlight.command_handler = self.command_handler

        self.torchlight.game_events.HookEx("server_spawn", self.Event_ServerSpawn)
        self.torchlight.game_events.HookEx("player_say", self.Event_PlayerSay)

    def OnReload(self) -> None:
        # self.command_handler.needs_reload = True
        self.logger.info("Full configuration reload triggered")
        # config.json was already re-read by Torchlight.Reload() before this callback.
        self.access_manager.Load()
        self.trigger_manager.Load()
        self.sourcemod_config.Load()
        for player in self.player_manager.players:
            if player:
                admin_override = self.access_manager.get_admin(unique_id=player.unique_id)
                if admin_override is not None:
                    player.admin = admin_override
                    self.logger.info(f"Updated {player.name} with new admin level: {player.admin.level}")
        self.audio_manager.anti_spam.config = self.config["AntiSpam"]
        self.audio_manager.advertiser.config = self.config["Advertiser"]
        self.command_handler.Reload()
        self.logger.info("Configuration reload completed")

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
        self.torchlight.disabled = None

    # @profile
    def Event_PlayerSay(self, userid: int, text: str) -> None:
        if userid == 0:
            return

        player = self.player_manager.FindUserID(userid)
        if player is None:
            return

        Utils.FireAndForget(self.command_handler.HandleCommand(text, player), self.logger)

    def OnPublish(self, obj: dict[str, str]) -> None:
        self.torchlight.OnPublish(obj)

    def OnDisconnect(self, exc: Exception | None) -> None:
        self.logger.info(f"OnDisconnect({exc})")

        if self.shutting_down:
            return

        # A _Connect() still running for the dead link must not touch the new graph.
        self._CancelConnect()

        previous_torchlight = self.torchlight
        previous_audio_manager = self.audio_manager
        previous_command_handler = self.command_handler
        try:
            self.Init()
        finally:
            # Nothing can reach the previous graph once Init() rebound self.*, so stop its
            # clips and close its commands now rather than letting them run orphaned.
            self._TeardownGraph(previous_torchlight, previous_audio_manager, previous_command_handler)

        self._StartConnect()

    def _TeardownGraph(
        self,
        torchlight: Torchlight,
        audio_manager: AudioManager,
        command_handler: CommandHandler,
    ) -> asyncio.Task:
        # Refuse new clips/commands on this graph: a command still awaiting (e.g. a !yt
        # resolving its URL) would otherwise start a clip nothing can reach or stop.
        torchlight.disabled = sys.maxsize

        # Stop() kills the ffmpeg process, voice-server socket and HTTP stream; its Stop
        # callback removes the clip from audio_clips and releases the clip's closures.
        for audio_clip in audio_manager.audio_clips[:]:
            try:
                audio_clip.Stop()
            except Exception:
                self.logger.error(traceback.format_exc())
        audio_manager.audio_clips.clear()

        for command in command_handler.commands:
            try:
                command.close()
            except Exception:
                self.logger.error(traceback.format_exc())
        command_handler.commands.clear()

        return Utils.FireAndForget(torchlight.flaresolverr.close(), self.logger)

    async def Shutdown(self) -> None:
        if self.shutting_down:
            return

        self.logger.info("Shutting down")
        self.shutting_down = True
        self.connection_generation += 1
        self._CancelConnect()

        await self._TeardownGraph(self.torchlight, self.audio_manager, self.command_handler)

    def __del__(self) -> None:
        self.logger.debug("~TorchlightHandler()")
