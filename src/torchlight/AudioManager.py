#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
from typing import List, Optional

from torchlight.Advertiser import Advertiser
from torchlight.AntiSpam import AntiSpam
from torchlight.AudioClip import AudioClip
from torchlight.AudioPlayerFactory import AudioPlayerFactory, AudioPlayerType
from torchlight.FFmpegAudioPlayer import FFmpegAudioPlayer
from torchlight.Player import Player
from torchlight.Torchlight import Torchlight


class AudioManager:
    def __init__(self, torchlight: Torchlight) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.anti_spam = AntiSpam(self.torchlight)
        self.advertiser = Advertiser(self.torchlight)
        self.audio_player_factory = AudioPlayerFactory()
        self.audio_clips: List[AudioClip] = []

    def __del__(self) -> None:
        self.logger.info("~AudioManager()")

    def CheckLimits(self, player: Player) -> bool:
        level: int = 0
        if player.access:
            level = player.access.level

        if str(level) in self.anti_spam.config:
            if (
                self.anti_spam.config[str(level)]["Uses"] >= 0
                and player.storage["Audio"]["Uses"]
                >= self.anti_spam.config[str(level)]["Uses"]
            ):

                self.torchlight.SayPrivate(
                    player,
                    "You have used up all of your free uses! ({0} uses)".format(
                        self.anti_spam.config[str(level)]["Uses"]
                    ),
                )
                return False

            if (
                player.storage["Audio"]["TimeUsed"]
                >= self.anti_spam.config[str(level)]["TotalTime"]
            ):
                self.torchlight.SayPrivate(
                    player,
                    "You have used up all of your free time! ({0} seconds)".format(
                        self.anti_spam.config[str(level)]["TotalTime"]
                    ),
                )
                return False

            time_elapsed = (
                self.torchlight.loop.time() - player.storage["Audio"]["LastUse"]
            )
            use_delay = (
                player.storage["Audio"]["LastUseLength"]
                * self.anti_spam.config[str(level)]["DelayFactor"]
            )

            if time_elapsed < use_delay:
                self.torchlight.SayPrivate(
                    player,
                    "You are currently on cooldown! ({0} seconds left)".format(
                        round(use_delay - time_elapsed)
                    ),
                )
                return False

        return True

    def Stop(self, player: Player, extra: str) -> None:
        level: int = 0
        if player.access:
            level = player.access.level

        for audio_clip in self.audio_clips[:]:
            if extra and not extra.lower() in audio_clip.player.name.lower():
                continue

            if not level or (
                level < audio_clip.level and level < self.anti_spam.config["StopLevel"]
            ):
                audio_clip.stops.add(player.user_id)

                if len(audio_clip.stops) >= 3:
                    audio_clip.Stop()
                    self.torchlight.SayPrivate(
                        audio_clip.player, "Your audio clip was stopped."
                    )
                    if player != audio_clip.player:
                        self.torchlight.SayPrivate(
                            player,
                            'Stopped "{0}"({1}) audio clip.'.format(
                                audio_clip.player.name, audio_clip.player.user_id
                            ),
                        )
                else:
                    self.torchlight.SayPrivate(
                        player,
                        "This audio clip needs {0} more !stop's.".format(
                            3 - len(audio_clip.stops)
                        ),
                    )
            else:
                audio_clip.Stop()
                self.torchlight.SayPrivate(
                    audio_clip.player, "Your audio clip was stopped."
                )
                if player != audio_clip.player:
                    self.torchlight.SayPrivate(
                        player,
                        'Stopped "{0}"({1}) audio clip.'.format(
                            audio_clip.player.name, audio_clip.player.user_id
                        ),
                    )

    def AudioClip(
        self,
        player: Player,
        uri: str,
        _type: AudioPlayerType = AudioPlayerType.AUDIOPLAYER_FFMPEG,
    ) -> Optional[AudioClip]:
        level: int = 0
        if player.access:
            level = player.access.level

        if self.torchlight.disabled and self.torchlight.disabled > level:
            self.torchlight.SayPrivate(player, "Torchlight is currently disabled!")
            return None

        if not self.anti_spam.CheckAntiSpam(player):
            return None

        if not self.CheckLimits(player):
            return None

        audio_player: FFmpegAudioPlayer = self.audio_player_factory.NewPlayer(
            _type, self.torchlight
        )
        clip = AudioClip(player, uri, audio_player, self.torchlight)
        self.audio_clips.append(clip)
        audio_player.AddCallback("Stop", lambda: self.audio_clips.remove(clip))

        if (
            not player.access
            or player.access.level < self.anti_spam.config["ImmunityLevel"]
        ):
            clip.audio_player.AddCallback(
                "Play", lambda *args: self.anti_spam.OnPlay(clip, *args)
            )
            clip.audio_player.AddCallback(
                "Stop", lambda *args: self.anti_spam.OnStop(clip, *args)
            )
            clip.audio_player.AddCallback(
                "Update",
                lambda *args: self.anti_spam.OnUpdate(self.audio_clips, clip, *args),
            )

        clip.audio_player.AddCallback(
            "Play", lambda *args: self.advertiser.OnPlay(clip, *args)
        )
        clip.audio_player.AddCallback(
            "Stop", lambda *args: self.advertiser.OnStop(clip, *args)
        )
        clip.audio_player.AddCallback(
            "Update", lambda *args: self.advertiser.OnUpdate(clip, *args)
        )

        return clip

    def OnDisconnect(self, player: Player) -> None:
        for audio_clip in self.audio_clips[:]:
            if audio_clip.player == player:
                audio_clip.Stop()
