import asyncio
import logging
import textwrap
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from torchlight.AsyncClient import AsyncClient
from torchlight.Config import Config
from torchlight.Player import Player
from torchlight.SourceModAPI import SourceModAPI
from torchlight.Subscribe import Forwards, GameEvents


class Torchlight:
    VALID_CALLBACKS = ["OnReload"]

    def __init__(
        self, config: Config, loop: asyncio.AbstractEventLoop, async_client: AsyncClient
    ):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.loop = loop
        self.async_client = async_client
        self.last_url = ""

        self.API = SourceModAPI(self.async_client)
        self.game_events = GameEvents(self.async_client)
        self.forwards = Forwards(self.async_client)

        self.disable_votes: Set = set()
        self.disabled = 0

        self.Callbacks: List[Tuple[str, Callable]] = []

    def Reload(self) -> None:
        self.config.Load()
        self.Callback("OnReload")

    def AddCallback(self, cbtype: str, cbfunc: Callable) -> bool:
        if cbtype not in self.VALID_CALLBACKS:
            return False

        self.Callbacks.append((cbtype, cbfunc))
        return True

    def Callback(self, cbtype: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.Callbacks:
            if callback[0] == cbtype:
                try:
                    callback[1](*args, **kwargs)
                except Exception:
                    self.Logger.error(traceback.format_exc())

    def OnPublish(self, obj: Dict[str, str]) -> None:
        if obj["module"] == "gameevents":
            self.game_events.OnPublish(obj)
        elif obj["module"] == "forwards":
            self.forwards.OnPublish(obj)

    def SayChat(self, message: str, player: Optional[Player] = None) -> None:
        message = f"{{darkblue}}[Torchlight]: {{default}}{message}"
        if len(message) > 976:
            message = message[:973] + "..."
        lines = textwrap.wrap(message, 244, break_long_words=True)
        for line in lines:
            asyncio.ensure_future(self.API.CPrintToChatAll(line))

        if player:
            Level = 0
            if player.access:
                Level = player.access.level

            if Level < self.config["AntiSpam"]["ImmunityLevel"]:
                cooldown = len(lines) * self.config["AntiSpam"]["ChatCooldown"]
                if player.ChatCooldown > self.loop.time():
                    player.ChatCooldown += cooldown
                else:
                    player.ChatCooldown = self.loop.time() + cooldown

    def SayPrivate(self, player: Player, message: str) -> None:
        message = f"{{darkblue}}[Torchlight]: {{default}}{message}"
        if len(message) > 976:
            message = message[:973] + "..."
        lines = textwrap.wrap(message, 244, break_long_words=True)
        for line in lines:
            asyncio.ensure_future(self.API.CPrintToChat(player.Index, line))

    def __del__(self) -> None:
        self.Logger.debug("~Torchlight()")
