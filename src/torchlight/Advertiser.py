import logging
import math
from typing import Any, Dict

from torchlight.AudioClip import AudioClip
from torchlight.Torchlight import Torchlight


class Advertiser:
    def __init__(self, torchlight: Torchlight) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.config = self.torchlight.config["Advertiser"]

        self.LastClips: Dict[int, Any] = dict()
        self.AdStop = 0
        self.NextAdStop = 0

    def Think(self, Delta: int) -> None:
        Now = self.torchlight.loop.time()
        Duration = 0.0

        for Key, Clip in list(self.LastClips.items()):
            if not Clip["timestamp"]:
                continue

            if Clip["timestamp"] + Clip["duration"] + self.config["MaxSpan"] < Now:
                if not Clip["active"]:
                    del self.LastClips[Key]
                continue

            Duration += Clip["duration"]

        self.NextAdStop -= Delta
        CeilDur = math.ceil(Duration)
        if (
            CeilDur > self.AdStop
            and self.NextAdStop <= 0
            and CeilDur % self.config["AdStop"] == 0
        ):
            self.torchlight.SayChat(
                "Hint: Type {{darkred}}!stop{{default}} to stop all currently playing sounds."
            )
            self.AdStop = CeilDur
            self.NextAdStop = 0
        elif CeilDur < self.AdStop:
            self.AdStop = 0
            self.NextAdStop = self.config["AdStop"] / 2

    def OnPlay(self, clip: AudioClip) -> None:
        Now = self.torchlight.loop.time()
        self.LastClips[hash(clip)] = dict(
            {"timestamp": Now, "duration": 0.0, "dominant": False, "active": True}
        )

        HasDominant = False
        for _, Clip in self.LastClips.items():
            if Clip["dominant"]:
                HasDominant = True
                break

        self.LastClips[hash(clip)]["dominant"] = not HasDominant

    def OnStop(self, clip: AudioClip) -> None:
        if hash(clip) not in self.LastClips:
            return

        self.LastClips[hash(clip)]["active"] = False

        if self.LastClips[hash(clip)]["dominant"]:
            for _, Clip in self.LastClips.items():
                if Clip["active"]:
                    Clip["dominant"] = True
                    break

        self.LastClips[hash(clip)]["dominant"] = False

    def OnUpdate(self, clip: AudioClip, old_position: int, new_position: int) -> None:
        Delta = new_position - old_position
        Clip = self.LastClips[hash(clip)]

        if not Clip["dominant"]:
            return

        Clip["duration"] += Delta
        self.Think(Delta)
