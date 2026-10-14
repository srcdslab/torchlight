import itertools
import logging
import sys
import time
from collections.abc import Callable
from typing import Any

from torchlight.FFmpegAudioPlayer import FFmpegAudioPlayer
from torchlight.Player import Player
from torchlight.Torchlight import Torchlight


class AudioClip:
    # Unique, monotonically increasing clip ids. AntiSpam and Advertiser key their usage
    # windows by it: unlike hash()/id(), an id is never handed to another clip once this
    # one has been freed, so a finished clip's entry cannot be overwritten (#182).
    _id_counter = itertools.count(1)

    def __init__(
        self,
        player: Player,
        uri: str,
        audio_player: FFmpegAudioPlayer,
        torchlight: Torchlight,
        on_start: Callable[["AudioClip"], None] | None = None,
    ):
        self.clip_id: int = next(AudioClip._id_counter)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight: Torchlight = torchlight
        self.config = self.torchlight.config["AudioLimits"]
        self.player = player
        self.audio_player = audio_player
        self.uri = uri
        self.last_position: int = 0
        self.stops: set[int] = set()

        self.level = self.player.admin.level

        # Called once with this clip when Play() has started playback, so the owner can
        # register it. Until then nothing references the clip but its creator: the player
        # callbacks (which close over the clip) are only wired in Play() as well, so a clip
        # that is never played is freed by refcounting instead of lingering (#182).
        self.on_start = on_start
        self.started = False

    def __del__(self) -> None:
        self.logger.debug("~AudioClip()")

    def SetDuration(self, duration: float) -> None:
        self.audio_player.SetDuration(duration)

    def Play(
        self,
        seconds: int | None = None,
        duration: int | None = None,
        *args: Any,
        volume: float | None = None,
        speed: float | None = None,
        pitch: float | None = None,
        needs_cf_bypass: bool = False,
    ) -> bool:
        if not self.audio_player.PlayURI(
            self.uri, seconds, duration, *args, volume=volume, speed=speed, pitch=pitch, needs_cf_bypass=needs_cf_bypass
        ):
            return False

        if not self.started:
            # PlayURI() only schedules the stream task, so no Play/Stop/Update callback can
            # fire before these are wired. Wiring them only once playback has started keeps
            # an unplayed clip out of a clip -> player -> callback -> clip cycle.
            self.started = True
            self.audio_player.AddCallback("Play", self.OnPlay)
            self.audio_player.AddCallback("Stop", self.OnStop)
            self.audio_player.AddCallback("Update", self.OnUpdate)

            on_start, self.on_start = self.on_start, None
            if on_start is not None:
                on_start(self)

        return True

    def Stop(self) -> bool:
        return self.audio_player.Stop()

    def OnPlay(self) -> None:
        self.logger.debug(sys._getframe().f_code.co_name + " " + self.uri)

        self.player.storage["Audio"]["Uses"] += 1
        self.player.storage["Audio"]["LastUse"] = self.torchlight.loop.time()
        self.player.storage["Audio"]["LastUseLength"] = 0.0

    def OnStop(self) -> None:
        self.logger.debug(sys._getframe().f_code.co_name + " " + self.uri)

        if self.audio_player.started_playing is not None:
            seconds_elapsed = time.time() - self.audio_player.started_playing
            delta = seconds_elapsed - self.last_position
            if delta > 0:
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
