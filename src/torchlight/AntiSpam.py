import logging
import math
from typing import Any, Dict, List

from torchlight.AudioClip import AudioClip
from torchlight.Player import Player
from torchlight.Torchlight import Torchlight


class AntiSpam:
    def __init__(self, torchlight: Torchlight) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.config = self.torchlight.config["AntiSpam"]

        self.LastClips: Dict[int, Any] = dict()
        self.DisabledTime = None
        self.SaidHint = False

    def CheckAntiSpam(self, player: Player) -> bool:
        if (
            self.DisabledTime
            and self.DisabledTime > self.torchlight.loop.time()
            and not (
                player.Access and player.Access["level"] >= self.config["ImmunityLevel"]
            )
        ):

            self.torchlight.SayPrivate(
                player,
                "Torchlight is currently on cooldown! ({0} seconds left)".format(
                    math.ceil(self.DisabledTime - self.torchlight.loop.time())
                ),
            )
            return False

        return True

    def SpamCheck(self, audio_clips: List[AudioClip], Delta: int) -> None:
        Now = self.torchlight.loop.time()
        Duration = 0.0

        for Key, Clip in list(self.LastClips.items()):
            if not Clip["timestamp"]:
                continue

            if Clip["timestamp"] + Clip["duration"] + self.config["MaxUsageSpan"] < Now:
                if not Clip["active"]:
                    del self.LastClips[Key]
                continue

            Duration += Clip["duration"]

        if Duration > self.config["MaxUsageTime"]:
            self.DisabledTime = self.torchlight.loop.time() + self.config["PunishDelay"]
            self.torchlight.SayChat(
                "Blocked voice commands for the next {0} seconds. Used {1} seconds within {2} seconds.".format(
                    self.config["PunishDelay"],
                    self.config["MaxUsageTime"],
                    self.config["MaxUsageSpan"],
                )
            )

            # Make a copy of the list since AudioClip.Stop() will change the list
            for AudioClip in audio_clips[:]:
                if AudioClip.Level < self.config["ImmunityLevel"]:
                    AudioClip.Stop()

            self.LastClips.clear()

    def OnPlay(self, clip: AudioClip) -> None:
        Now = self.torchlight.loop.time()
        self.LastClips[hash(clip)] = dict(
            {"timestamp": Now, "duration": 0.0, "dominant": False, "active": True}
        )

        HasDominant = False
        for Key, Clip in self.LastClips.items():
            if Clip["dominant"]:
                HasDominant = True
                break

        self.LastClips[hash(clip)]["dominant"] = not HasDominant

    def OnStop(self, clip: AudioClip) -> None:
        if hash(clip) not in self.LastClips:
            return

        self.LastClips[hash(clip)]["active"] = False

        if self.LastClips[hash(clip)]["dominant"]:
            for Key, Clip in self.LastClips.items():
                if Clip["active"]:
                    Clip["dominant"] = True
                    break

        self.LastClips[hash(clip)]["dominant"] = False

    def OnUpdate(
        self,
        audio_clips: List[AudioClip],
        clip: AudioClip,
        old_position: int,
        new_position: int,
    ) -> None:
        Delta = new_position - old_position
        Clip = self.LastClips[hash(clip)]

        if not Clip["dominant"]:
            return

        Clip["duration"] += Delta
        self.SpamCheck(audio_clips, Delta)
