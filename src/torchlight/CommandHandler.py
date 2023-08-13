import logging
import sys
import traceback
from importlib import reload
from re import Match
from typing import Any

from torchlight.AccessManager import AccessManager
from torchlight.AudioManager import AudioManager
from torchlight.Commands import BaseCommand, VoiceTrigger
from torchlight.PlayerManager import Player, PlayerManager
from torchlight.Torchlight import Torchlight


class CommandHandler:
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.access_manager = access_manager
        self.player_manager = player_manager
        self.audio_manager = audio_manager
        self.commands: list[BaseCommand] = []
        self.needs_reload = False

    def Setup(self) -> None:
        counter = len(self.commands)
        self.commands.clear()
        if counter:
            self.logger.info(
                sys._getframe().f_code.co_name
                + f" Unloaded {counter} commands!"
            )

        counter = 0
        subklasses: list[type[Any]] = []
        subklasses.extend(BaseCommand.__subclasses__())
        subklasses.extend(VoiceTrigger.__subclasses__())
        for subklass in sorted(subklasses, key=lambda x: x.order, reverse=True):
            try:
                command = subklass(
                    self.torchlight,
                    self.access_manager,
                    self.player_manager,
                    self.audio_manager,
                )
                if hasattr(command, "_setup"):
                    command._setup()
            except Exception:
                self.logger.error(traceback.format_exc())
            else:
                self.commands.append(command)
                counter += 1

        self.logger.info(
            sys._getframe().f_code.co_name + f" Loaded {counter} commands!"
        )

    def Reload(self) -> None:
        from . import Commands

        try:
            reload(Commands)
        except Exception:
            self.logger.error(traceback.format_exc())
        else:
            self.Setup()

    async def HandleCommand(self, line: str, player: Player) -> int | None:
        message = line.split(sep=" ", maxsplit=1)
        if len(message) < 2:
            message.append("")
        message[1] = message[1].strip()

        if message[1] and self.torchlight.last_url:
            message[1] = message[1].replace("!last", self.torchlight.last_url)
            line = message[0] + " " + message[1]

        level = player.access.level

        self.logger.debug(f"Command: {message}")
        ret_message: str | None = None
        ret: int | None = None
        for command in self.commands:
            for trigger in command.triggers:
                is_match = False
                r_match: Match | None = None
                self.logger.debug(type(trigger))
                self.logger.debug(f"Trigger: {trigger}")
                if isinstance(trigger, tuple):
                    if message[0].lower().startswith(trigger[0], 0, trigger[1]):
                        is_match = True
                elif isinstance(trigger, str):
                    if message[0].lower() == trigger.lower():
                        is_match = True
                else:  # compiled regex
                    r_match = trigger.search(line)
                    if r_match:
                        is_match = True

                if not is_match:
                    continue

                self.logger.debug(
                    sys._getframe().f_code.co_name
                    + ' "{}" Match -> {} | {}'.format(
                        player.name, command.__class__.__name__, trigger
                    )
                )

                if level < command.level:
                    ret_message = "You do not have access to this command! (You: {} | Required: {})".format(
                        level, command.level
                    )
                    continue

                try:
                    if r_match is not None:
                        ret_temp = await command._rfunc(line, r_match, player)

                        if isinstance(ret_temp, str):
                            message = ret_temp.split(sep=" ", maxsplit=1)
                            ret = None
                        else:
                            ret = ret_temp
                    else:
                        ret = await command._func(message, player)
                except Exception as e:
                    self.logger.error(traceback.format_exc())
                    self.torchlight.SayChat(f"Error: {str(e)}")

                ret_message = None

                if ret is not None and ret > 0:
                    break

            if ret is not None and ret >= 0:
                break

        if ret_message:
            self.torchlight.SayPrivate(player, ret_message)

        if self.needs_reload:
            self.needs_reload = False
            self.Reload()

        return ret
