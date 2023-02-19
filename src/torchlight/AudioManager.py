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
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.AntiSpam = AntiSpam(self.torchlight)
        self.Advertiser = Advertiser(self.torchlight)
        self.AudioPlayerFactory = AudioPlayerFactory()
        self.AudioClips: List[AudioClip] = []

    def __del__(self) -> None:
        self.Logger.info("~AudioManager()")

    def CheckLimits(self, player: Player) -> bool:
        Level: int = 0
        if player.access:
            Level = player.access.level

        if str(Level) in self.AntiSpam.config:
            if (
                self.AntiSpam.config[str(Level)]["Uses"] >= 0
                and player.Storage["Audio"]["Uses"]
                >= self.AntiSpam.config[str(Level)]["Uses"]
            ):

                self.torchlight.SayPrivate(
                    player,
                    "You have used up all of your free uses! ({0} uses)".format(
                        self.AntiSpam.config[str(Level)]["Uses"]
                    ),
                )
                return False

            if (
                player.Storage["Audio"]["TimeUsed"]
                >= self.AntiSpam.config[str(Level)]["TotalTime"]
            ):
                self.torchlight.SayPrivate(
                    player,
                    "You have used up all of your free time! ({0} seconds)".format(
                        self.AntiSpam.config[str(Level)]["TotalTime"]
                    ),
                )
                return False

            TimeElapsed = (
                self.torchlight.loop.time() - player.Storage["Audio"]["LastUse"]
            )
            UseDelay = (
                player.Storage["Audio"]["LastUseLength"]
                * self.AntiSpam.config[str(Level)]["DelayFactor"]
            )

            if TimeElapsed < UseDelay:
                self.torchlight.SayPrivate(
                    player,
                    "You are currently on cooldown! ({0} seconds left)".format(
                        round(UseDelay - TimeElapsed)
                    ),
                )
                return False

        return True

    def Stop(self, player: Player, extra: str) -> None:
        Level: int = 0
        if player.access:
            Level = player.access.level

        for AudioClip in self.AudioClips[:]:
            if extra and not extra.lower() in AudioClip.player.Name.lower():
                continue

            if not Level or (
                Level < AudioClip.Level and Level < self.AntiSpam.config["StopLevel"]
            ):
                AudioClip.Stops.add(player.UserID)

                if len(AudioClip.Stops) >= 3:
                    AudioClip.Stop()
                    self.torchlight.SayPrivate(
                        AudioClip.player, "Your audio clip was stopped."
                    )
                    if player != AudioClip.player:
                        self.torchlight.SayPrivate(
                            player,
                            'Stopped "{0}"({1}) audio clip.'.format(
                                AudioClip.player.Name, AudioClip.player.UserID
                            ),
                        )
                else:
                    self.torchlight.SayPrivate(
                        player,
                        "This audio clip needs {0} more !stop's.".format(
                            3 - len(AudioClip.Stops)
                        ),
                    )
            else:
                AudioClip.Stop()
                self.torchlight.SayPrivate(
                    AudioClip.player, "Your audio clip was stopped."
                )
                if player != AudioClip.player:
                    self.torchlight.SayPrivate(
                        player,
                        'Stopped "{0}"({1}) audio clip.'.format(
                            AudioClip.player.Name, AudioClip.player.UserID
                        ),
                    )

    def AudioClip(
        self,
        player: Player,
        uri: str,
        _type: AudioPlayerType = AudioPlayerType.AUDIOPLAYER_FFMPEG,
    ) -> Optional[AudioClip]:
        Level: int = 0
        if player.access:
            Level = player.access.level

        if self.torchlight.disabled and self.torchlight.disabled > Level:
            self.torchlight.SayPrivate(player, "Torchlight is currently disabled!")
            return None

        if not self.AntiSpam.CheckAntiSpam(player):
            return None

        if not self.CheckLimits(player):
            return None

        audio_player: FFmpegAudioPlayer = self.AudioPlayerFactory.NewPlayer(
            _type, self.torchlight
        )
        Clip = AudioClip(player, uri, audio_player, self.torchlight)
        self.AudioClips.append(Clip)
        audio_player.AddCallback("Stop", lambda: self.AudioClips.remove(Clip))

        if (
            not player.access
            or player.access.level < self.AntiSpam.config["ImmunityLevel"]
        ):
            Clip.audio_player.AddCallback(
                "Play", lambda *args: self.AntiSpam.OnPlay(Clip, *args)
            )
            Clip.audio_player.AddCallback(
                "Stop", lambda *args: self.AntiSpam.OnStop(Clip, *args)
            )
            Clip.audio_player.AddCallback(
                "Update",
                lambda *args: self.AntiSpam.OnUpdate(self.AudioClips, Clip, *args),
            )

        Clip.audio_player.AddCallback(
            "Play", lambda *args: self.Advertiser.OnPlay(Clip, *args)
        )
        Clip.audio_player.AddCallback(
            "Stop", lambda *args: self.Advertiser.OnStop(Clip, *args)
        )
        Clip.audio_player.AddCallback(
            "Update", lambda *args: self.Advertiser.OnUpdate(Clip, *args)
        )

        return Clip

    def OnDisconnect(self, player: Player) -> None:
        for AudioClip in self.AudioClips[:]:
            if AudioClip.player == player:
                AudioClip.Stop()
