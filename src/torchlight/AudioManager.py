import logging

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
        self.audio_clips: list[AudioClip] = []

    def __del__(self) -> None:
        self.logger.info("~AudioManager()")

    def CheckLimits(self, player: Player) -> bool:
        level = player.admin.level

        if str(level) in self.anti_spam.config:
            if (
                self.anti_spam.config[str(level)]["Uses"] >= 0
                and player.storage["Audio"]["Uses"] >= self.anti_spam.config[str(level)]["Uses"]
            ):
                self.torchlight.SayPrivate(
                    player,
                    "You have used up all of your free uses! ({} uses)".format(
                        self.anti_spam.config[str(level)]["Uses"]
                    ),
                )
                return False

            if player.storage["Audio"]["TimeUsed"] >= self.anti_spam.config[str(level)]["TotalTime"]:
                self.torchlight.SayPrivate(
                    player,
                    "You have used up all of your free time! ({} seconds)".format(
                        self.anti_spam.config[str(level)]["TotalTime"]
                    ),
                )
                return False

            time_elapsed = self.torchlight.loop.time() - player.storage["Audio"]["LastUse"]
            use_delay = player.storage["Audio"]["LastUseLength"] * self.anti_spam.config[str(level)]["DelayFactor"]

            if time_elapsed < use_delay:
                self.torchlight.SayPrivate(
                    player,
                    f"You are currently on cooldown! ({round(use_delay - time_elapsed)} seconds left)",
                )
                return False

        return True

    def Stop(self, player: Player, extra: str) -> None:
        level = player.admin.level
        stop_level = self.anti_spam.config.get("StopLevel", 3)
        self.logger.info(f"Stop called by {player.name} (level {level}), extra='{extra}'")
        self.logger.info(f"Currently playing {len(self.audio_clips)} audio clip(s).")

        if not self.audio_clips:
            self.torchlight.SayPrivate(player, "No audio is currently playing.")
            return

        stopped_count = 0

        for audio_clip in self.audio_clips[:]:
            clip_player = audio_clip.player
            clip_level = audio_clip.level
            self.logger.info(f"Checking clip: {clip_player.name} (level {clip_level}) playing {audio_clip.uri}")

            if extra and extra.lower() not in audio_clip.player.name.lower():
                continue

            can_stop = False
            reason = ""
            if player.user_id == clip_player.user_id:
                can_stop = True
                reason = "stopped own sound"
            elif level >= stop_level:
                can_stop = True
                reason = f"admin (level {level} >= {stop_level})"
            elif level > clip_level:
                can_stop = True
                reason = f"higher level (level {level} > {clip_level})"
            else:
                audio_clip.stops.add(player.user_id)
                votes_needed = 3 - len(audio_clip.stops)
                if votes_needed <= 0:
                    can_stop = True
                    reason = "vote passed"
                else:
                    self.torchlight.SayPrivate(
                        player,
                        f"Need {votes_needed} more !stop(s) to stop {clip_player.name}'s sound.",
                    )
                    continue
            if can_stop:
                self.logger.info(f"Stopping clip: {reason}")
                if audio_clip.Stop():
                    stopped_count += 1
                    if player.user_id != clip_player.user_id:
                        self.torchlight.SayPrivate(
                            clip_player,
                            f"Your audio was stopped by {player.name}.",
                        )
        if stopped_count > 0:
            if stopped_count == 1:
                self.torchlight.SayPrivate(player, f"Stopped {stopped_count} audio clip.")
            else:
                self.torchlight.SayPrivate(player, f"Stopped {stopped_count} audio clips.")
        elif not extra:
            self.torchlight.SayPrivate(
                player,
                "No audio clips matched your request. Use '!stop playername' to target specific player.",
            )

    def StopAll(self) -> None:
        self.logger.info("Force stopping all audio clips from all users.")
        for audio_clip in self.audio_clips[:]:
            try:
                audio_clip.Stop()
            except Exception as e:
                self.logger.error(f"Error stopping audio clip: {e}")
            self.torchlight.SayPrivate(audio_clip.player, "All audio has been force-stopped by admin.")
        self.audio_clips.clear()

    def AudioClip(
        self,
        player: Player,
        uri: str,
        _type: AudioPlayerType = AudioPlayerType.AUDIOPLAYER_FFMPEG,
    ) -> AudioClip | None:
        level = player.admin.level

        if self.torchlight.disabled and self.torchlight.disabled > level:
            self.torchlight.SayPrivate(player, "Torchlight is currently disabled!")
            return None

        if not self.anti_spam.CheckAntiSpam(player):
            return None

        if not self.CheckLimits(player):
            return None

        audio_player: FFmpegAudioPlayer = self.audio_player_factory.NewPlayer(_type, self.torchlight)
        clip = AudioClip(player, uri, audio_player, self.torchlight)
        self.audio_clips.append(clip)
        audio_player.AddCallback("Stop", lambda: self.audio_clips.remove(clip))

        if player.admin.level < self.anti_spam.config["ImmunityLevel"]:
            clip.audio_player.AddCallback("Play", lambda *args: self.anti_spam.OnPlay(clip, *args))
            clip.audio_player.AddCallback("Stop", lambda *args: self.anti_spam.OnStop(clip, *args))
            clip.audio_player.AddCallback(
                "Update",
                lambda *args: self.anti_spam.OnUpdate(self.audio_clips, clip, *args),
            )

        clip.audio_player.AddCallback("Play", lambda *args: self.advertiser.OnPlay(clip, *args))
        clip.audio_player.AddCallback("Stop", lambda *args: self.advertiser.OnStop(clip, *args))
        clip.audio_player.AddCallback("Update", lambda *args: self.advertiser.OnUpdate(clip, *args))

        return clip

    def OnDisconnect(self, player: Player) -> None:
        for audio_clip in self.audio_clips[:]:
            if audio_clip.player.unique_id == player.unique_id:
                audio_clip.Stop()
