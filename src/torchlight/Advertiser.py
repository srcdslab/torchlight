import logging
import math
from typing import Any

from torchlight.AudioClip import AudioClip
from torchlight.Torchlight import Torchlight


class Advertiser:
    def __init__(self, torchlight: Torchlight) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.config = self.torchlight.config["Advertiser"]

        self.last_clips: dict[int, Any] = {}
        self.ad_stop = 0
        self.next_ad_stop = 0

    def Think(self, delta: int) -> None:
        now = self.torchlight.loop.time()
        duration = 0.0

        for key, clip in list(self.last_clips.items()):
            if not clip["timestamp"]:
                continue

            if clip["timestamp"] + clip["duration"] + self.config["MaxSpan"] < now:
                if not clip["active"]:
                    del self.last_clips[key]
                continue

            duration += clip["duration"]

        self.next_ad_stop -= delta
        ceil_duration = math.ceil(duration)
        if (
            ceil_duration > self.ad_stop
            and self.next_ad_stop <= 0
            and ceil_duration % self.config["AdStop"] == 0
        ):
            self.torchlight.SayChat(
                "Hint: Type {darkred}!stop{default} to stop all currently playing sounds."
            )
            self.ad_stop = ceil_duration
            self.next_ad_stop = 0
        elif ceil_duration < self.ad_stop:
            self.ad_stop = 0
            self.next_ad_stop = self.config["AdStop"] / 2

    def OnPlay(self, clip: AudioClip) -> None:
        now = self.torchlight.loop.time()
        self.last_clips[hash(clip)] = dict(
            {"timestamp": now, "duration": 0.0, "dominant": False, "active": True}
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

    def OnUpdate(self, clip: AudioClip, old_position: int, new_position: int) -> None:
        delta = new_position - old_position
        last_clip = self.last_clips[hash(clip)]

        if not last_clip["dominant"]:
            return

        last_clip["duration"] += delta
        self.Think(delta)
