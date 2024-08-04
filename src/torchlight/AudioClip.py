import logging
import sys
from typing import Any

from torchlight.FFmpegAudioPlayer import FFmpegAudioPlayer
from torchlight.Player import Player
from torchlight.Torchlight import Torchlight


class AudioClip:
    def __init__(
        self,
        player: Player,
        uri: str,
        audio_player: FFmpegAudioPlayer,
        torchlight: Torchlight,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight: Torchlight = torchlight
        self.config = self.torchlight.config["AudioLimits"]
        self.player = player
        self.audio_player = audio_player
        self.uri = uri
        self.last_position: int = 0
        self.stops: set[int] = set()

        self.level = self.player.admin.level

        self.audio_player.AddCallback("Play", self.OnPlay)
        self.audio_player.AddCallback("Stop", self.OnStop)
        self.audio_player.AddCallback("Update", self.OnUpdate)

    def __del__(self) -> None:
        self.logger.debug("~AudioClip()")

    def Play(self, seconds: int | None = None, *args: Any) -> bool:
        return self.audio_player.PlayURI(self.uri, seconds, *args)

    def Stop(self) -> bool:
        return self.audio_player.Stop()

    def OnPlay(self) -> None:
        self.logger.debug(sys._getframe().f_code.co_name + " " + self.uri)

        self.player.storage["Audio"]["Uses"] += 1
        self.player.storage["Audio"]["LastUse"] = self.torchlight.loop.time()
        self.player.storage["Audio"]["LastUseLength"] = 0.0

    def OnStop(self) -> None:
        self.logger.debug(sys._getframe().f_code.co_name + " " + self.uri)

        if self.audio_player.playing:
            delta = self.audio_player.position - self.last_position
            self.player.storage["Audio"]["TimeUsed"] += delta
            self.player.storage["Audio"]["LastUseLength"] += delta

        if str(self.level) in self.config:
            if self.player.storage:
                if self.player.storage["Audio"]["TimeUsed"] >= self.config[str(self.level)]["TotalTime"]:
                    self.torchlight.SayPrivate(
                        self.player,
                        "You have used up all of your free time! ({} seconds)".format(
                            self.config[str(self.level)]["TotalTime"]
                        ),
                    )
                elif self.player.storage["Audio"]["LastUseLength"] >= self.config[str(self.level)]["MaxLength"]:
                    self.torchlight.SayPrivate(
                        self.player,
                        "Your audio clip exceeded the maximum length! ({} seconds)".format(
                            self.config[str(self.level)]["MaxLength"]
                        ),
                    )

        del self.audio_player

    def OnUpdate(self, old_position: int, new_position: int) -> None:
        delta = new_position - old_position
        self.last_position = new_position

        self.player.storage["Audio"]["TimeUsed"] += delta
        self.player.storage["Audio"]["LastUseLength"] += delta

        if str(self.level) not in self.config:
            return

        if (
            self.player.storage["Audio"]["TimeUsed"] >= self.config[str(self.level)]["TotalTime"]
            or self.player.storage["Audio"]["LastUseLength"] >= self.config[str(self.level)]["MaxLength"]
        ):
            self.Stop()
