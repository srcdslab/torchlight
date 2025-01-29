import asyncio
import logging
import textwrap
import traceback
from collections.abc import Callable
from typing import Any

from torchlight.AsyncClient import AsyncClient
from torchlight.Config import Config
from torchlight.Player import Player
from torchlight.SourceModAPI import SourceModAPI
from torchlight.Subscribe import Forwards, GameEvents


class Torchlight:
    VALID_CALLBACKS = ["OnReload"]

    def __init__(
        self,
        config: Config,
        loop: asyncio.AbstractEventLoop,
        async_client: AsyncClient,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.loop = loop
        self.async_client = async_client
        self.last_url = ""

        self.sourcemod_api = SourceModAPI(self.async_client)
        self.game_events = GameEvents(self.async_client)
        self.forwards = Forwards(self.async_client)

        self.disable_votes: set = set()
        self.disabled = 0

        self.callbacks: list[tuple[str, Callable]] = []

    def Reload(self) -> None:
        self.config.load()
        self.Callback("OnReload")

    def AddCallback(self, cbtype: str, cbfunc: Callable) -> bool:
        if cbtype not in self.VALID_CALLBACKS:
            return False

        self.callbacks.append((cbtype, cbfunc))
        return True

    def Callback(self, cbtype: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            if callback[0] == cbtype:
                try:
                    callback[1](*args, **kwargs)
                except Exception:
                    self.logger.error(traceback.format_exc())

    # @profile
    def OnPublish(self, obj: dict[str, str]) -> None:
        if obj["module"] == "gameevents":
            self.game_events.OnPublish(obj)
        elif obj["module"] == "forwards":
            self.forwards.OnPublish(obj)

    # @profile
    def SayChat(self, message: str, player: Player | None = None) -> None:
        message = f"{{darkblue}}[Torchlight]: {{default}}{message}"
        if len(message) > 976:
            message = message[:973] + "..."
        lines = textwrap.wrap(message, 244, break_long_words=True)
        for line in lines:
            asyncio.ensure_future(self.sourcemod_api.CPrintToChatAll(line))

        if player:
            level = player.admin.level

            if level < self.config["AntiSpam"]["ImmunityLevel"]:
                cooldown = len(lines) * self.config["AntiSpam"]["ChatCooldown"]
                if player.chat_cooldown > self.loop.time():
                    player.chat_cooldown += cooldown
                else:
                    player.chat_cooldown = self.loop.time() + cooldown

    # @profile
    def SayPrivate(self, player: Player, message: str) -> None:
        if player.index == 0:
            return

        message = f"{{darkblue}}[Torchlight]: {{default}}{message}"
        if len(message) > 976:
            message = message[:973] + "..."
        lines = textwrap.wrap(message, 244, break_long_words=True)
        for line in lines:
            asyncio.ensure_future(self.sourcemod_api.CPrintToChat(player.index, line))

    def __del__(self) -> None:
        self.logger.debug("~Torchlight()")
