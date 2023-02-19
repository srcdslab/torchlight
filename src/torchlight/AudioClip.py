import logging
import sys
from typing import Any, Optional, Set

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
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight: Torchlight = torchlight
        self.config = self.torchlight.config["AudioLimits"]
        self.player = player
        self.audio_player = audio_player
        self.URI = uri
        self.LastPosition: int = 0
        self.Stops: Set[int] = set()

        self.Level = 0
        if self.player.access:
            self.Level = self.player.access.level

        self.audio_player.AddCallback("Play", self.OnPlay)
        self.audio_player.AddCallback("Stop", self.OnStop)
        self.audio_player.AddCallback("Update", self.OnUpdate)

    def __del__(self) -> None:
        self.Logger.info("~AudioClip()")

    def Play(self, seconds: Optional[int] = None, *args: Any) -> bool:
        return self.audio_player.PlayURI(self.URI, seconds, *args)

    def Stop(self) -> bool:
        return self.audio_player.Stop()

    def OnPlay(self) -> None:
        self.Logger.debug(sys._getframe().f_code.co_name + " " + self.URI)

        self.player.Storage["Audio"]["Uses"] += 1
        self.player.Storage["Audio"]["LastUse"] = self.torchlight.loop.time()
        self.player.Storage["Audio"]["LastUseLength"] = 0.0

    def OnStop(self) -> None:
        self.Logger.debug(sys._getframe().f_code.co_name + " " + self.URI)

        if self.audio_player.Playing:
            Delta = self.audio_player.Position - self.LastPosition
            self.player.Storage["Audio"]["TimeUsed"] += Delta
            self.player.Storage["Audio"]["LastUseLength"] += Delta

        if str(self.Level) in self.config:
            if self.player.Storage:
                if (
                    self.player.Storage["Audio"]["TimeUsed"]
                    >= self.config[str(self.Level)]["TotalTime"]
                ):
                    self.torchlight.SayPrivate(
                        self.player,
                        "You have used up all of your free time! ({0} seconds)".format(
                            self.config[str(self.Level)]["TotalTime"]
                        ),
                    )
                elif (
                    self.player.Storage["Audio"]["LastUseLength"]
                    >= self.config[str(self.Level)]["MaxLength"]
                ):
                    self.torchlight.SayPrivate(
                        self.player,
                        "Your audio clip exceeded the maximum length! ({0} seconds)".format(
                            self.config[str(self.Level)]["MaxLength"]
                        ),
                    )

        del self.audio_player

    def OnUpdate(self, old_position: int, new_position: int) -> None:
        Delta = new_position - old_position
        self.LastPosition = new_position

        self.player.Storage["Audio"]["TimeUsed"] += Delta
        self.player.Storage["Audio"]["LastUseLength"] += Delta

        if not str(self.Level) in self.config:
            return

        if (
            self.player.Storage["Audio"]["TimeUsed"]
            >= self.config[str(self.Level)]["TotalTime"]
            or self.player.Storage["Audio"]["LastUseLength"]
            >= self.config[str(self.Level)]["MaxLength"]
        ):
            self.Stop()
