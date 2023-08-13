import logging
import math
from typing import Any

from torchlight.AudioClip import AudioClip
from torchlight.Player import Player
from torchlight.Torchlight import Torchlight


class AntiSpam:
    def __init__(self, torchlight: Torchlight) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.config = self.torchlight.config["AntiSpam"]

        self.last_clips: dict[int, Any] = {}
        self.disabled_time = None
        self.said_hint = False

    def CheckAntiSpam(self, player: Player) -> bool:
        if (
            self.disabled_time
            and self.disabled_time > self.torchlight.loop.time()
            and player.access.level < self.config["ImmunityLevel"]
        ):
            self.torchlight.SayPrivate(
                player,
                "Torchlight is currently on cooldown! ({} seconds left)".format(
                    math.ceil(self.disabled_time - self.torchlight.loop.time())
                ),
            )
            return False

        return True

    def SpamCheck(self, audio_clips: list[AudioClip], delta: int) -> None:
        now = self.torchlight.loop.time()
        duration = 0.0

        for key, last_clip in list(self.last_clips.items()):
            if not last_clip["timestamp"]:
                continue

            if (
                last_clip["timestamp"]
                + last_clip["duration"]
                + self.config["MaxUsageSpan"]
                < now
            ):
                if not last_clip["active"]:
                    del self.last_clips[key]
                continue

            duration += last_clip["duration"]

        if duration > self.config["MaxUsageTime"]:
            self.disabled_time = (
                self.torchlight.loop.time() + self.config["PunishDelay"]
            )
            self.torchlight.SayChat(
                "Blocked voice commands for the next {} seconds. Used {} seconds within {} seconds.".format(
                    self.config["PunishDelay"],
                    self.config["MaxUsageTime"],
                    self.config["MaxUsageSpan"],
                )
            )

            # Make a copy of the list since AudioClip.Stop() will change the list
            for audio_clip in audio_clips[:]:
                if audio_clip.level < self.config["ImmunityLevel"]:
                    audio_clip.Stop()

            self.last_clips.clear()

    def OnPlay(self, clip: AudioClip) -> None:
        now = self.torchlight.loop.time()
        self.last_clips[hash(clip)] = dict(
            {
                "timestamp": now,
                "duration": 0.0,
                "dominant": False,
                "active": True,
            }
        )

        has_dominant = False
        for _, last_clip in self.last_clips.items():
            if last_clip["dominant"]:
                has_dominant = True
                break

        self.last_clips[hash(clip)]["dominant"] = not has_dominant

    def OnStop(self, clip: AudioClip) -> None:
        if hash(clip) not in self.last_clips:
            return

        self.last_clips[hash(clip)]["active"] = False

        if self.last_clips[hash(clip)]["dominant"]:
            for _, last_clip in self.last_clips.items():
                if last_clip["active"]:
                    last_clip["dominant"] = True
                    break

        self.last_clips[hash(clip)]["dominant"] = False

    def OnUpdate(
        self,
        audio_clips: list[AudioClip],
        clip: AudioClip,
        old_position: int,
        new_position: int,
    ) -> None:
        delta = new_position - old_position
        last_clip = self.last_clips[hash(clip)]

        if not last_clip["dominant"]:
            return

        last_clip["duration"] += delta
        self.SpamCheck(audio_clips, delta)
