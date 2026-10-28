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

    def ParseParams(self, trigger_params: dict, msg: str) -> dict[str, float]:
        this_config = self.torchlight.config.config.get("VoiceServer", {}).get("AudioParams", {})
        if not this_config:
            return trigger_params

        params: dict[str, float] = {}
        for param, config in this_config.items():
            if param in trigger_params and trigger_params[param] is not None:
                params[param] = float(trigger_params[param])
            else:
                if isinstance(config, dict) and "Default" in config:
                    params[param] = float(config["Default"])

        msg_args = msg.split()
        for arg in msg_args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                if not key or not value:
                    continue

                key = key.capitalize()

                if (key in this_config and isinstance(this_config[key], dict)) or key in ("Start", "End"):
                    try:
                        val = float(value)
                    except ValueError:
                        continue

                    if key in this_config:
                        if "Min" not in this_config[key] or "Max" not in this_config[key]:
                            continue

                        val = max(this_config[key]["Min"], min(val, this_config[key]["Max"]))
                        params[key] = val
                    else:
                        # Key here is either Start or End
                        params[key] = val

        return params

    def CheckLimits(self, player: Player) -> bool:
        # Per-level limits live in the AudioLimits section (the same source as
        # AudioClip and FormatAccess). Read them at call time so !reload applies.
        # A level without an entry, or no AudioLimits section at all, means no limits.
        limits = self.torchlight.config.config.get("AudioLimits", {}).get(str(player.admin.level))
        if not limits:
            return True

        audio_storage = player.storage["Audio"]

        # Negative Uses / TotalTime mean unlimited, consistent with FormatAccess.
        uses = limits.get("Uses", -1)
        if uses >= 0 and audio_storage["Uses"] >= uses:
            self.torchlight.SayPrivate(player, f"You have used up all of your free uses! ({uses} uses)")
            return False

        total_time = limits.get("TotalTime", -1)
        if total_time >= 0 and audio_storage["TimeUsed"] >= total_time:
            self.torchlight.SayPrivate(player, f"You have used up all of your free time! ({total_time} seconds)")
            return False

        time_elapsed = self.torchlight.loop.time() - audio_storage["LastUse"]
        use_delay = audio_storage["LastUseLength"] * limits.get("DelayFactor", 0)

        if time_elapsed < use_delay:
            self.torchlight.SayPrivate(
                player,
                f"You are currently on cooldown! ({round(use_delay - time_elapsed)} seconds left)",
            )
            return False

        return True

    def _StopClip(self, player: Player, audio_clip: AudioClip) -> None:
        audio_clip.Stop()
        self.torchlight.SayPrivate(audio_clip.player, "Your audio clip was stopped.")
        if player != audio_clip.player:
            self.torchlight.SayPrivate(
                player,
                f'Stopped "{audio_clip.player.name}"({audio_clip.player.user_id}) audio clip.',
            )

    def Stop(self, player: Player, extra: str) -> None:
        level = player.admin.level

        for audio_clip in self.audio_clips[:]:
            if extra and extra.lower() not in audio_clip.player.name.lower():
                continue

            if not level or (level < audio_clip.level and level < self.anti_spam.config["StopLevel"]):
                audio_clip.stops.add(player.user_id)

                if len(audio_clip.stops) >= 3:
                    self._StopClip(player, audio_clip)
                else:
                    self.torchlight.SayPrivate(
                        player,
                        f"This audio clip needs {3 - len(audio_clip.stops)} more !stop's.",
                    )
            else:
                self._StopClip(player, audio_clip)

    def AudioClip(
        self,
        player: Player,
        uri: str,
        _type: AudioPlayerType = AudioPlayerType.AUDIOPLAYER_FFMPEG,
    ) -> AudioClip | None:
        level = player.admin.level

        if self.torchlight.disabled is not None and self.torchlight.disabled > level:
            self.torchlight.SayPrivate(player, "Torchlight is currently disabled!")
            return None

        if not self.anti_spam.CheckAntiSpam(player):
            return None

        if not self.CheckLimits(player):
            return None

        def register(clip: AudioClip) -> None:
            # Only track the clip once AudioClip.Play() has started it: a clip whose caller
            # bails out before Play() never gets a Stop callback, so registering it up front
            # would leave it in audio_clips forever (#182).
            self.audio_clips.append(clip)
            clip.audio_player.AddCallback("Stop", lambda: self.audio_clips.remove(clip))

            if clip.level < self.anti_spam.config["ImmunityLevel"]:
                clip.audio_player.AddCallback("Play", lambda *args: self.anti_spam.OnPlay(clip, *args))
                clip.audio_player.AddCallback("Stop", lambda *args: self.anti_spam.OnStop(clip, *args))
                clip.audio_player.AddCallback(
                    "Update",
                    lambda *args: self.anti_spam.OnUpdate(self.audio_clips, clip, *args),
                )

            clip.audio_player.AddCallback("Play", lambda *args: self.advertiser.OnPlay(clip, *args))
            clip.audio_player.AddCallback("Stop", lambda *args: self.advertiser.OnStop(clip, *args))
            clip.audio_player.AddCallback("Update", lambda *args: self.advertiser.OnUpdate(clip, *args))

        audio_player: FFmpegAudioPlayer = self.audio_player_factory.NewPlayer(_type, self.torchlight)
        return AudioClip(player, uri, audio_player, self.torchlight, on_start=register)

    def OnDisconnect(self, player: Player) -> None:
        for audio_clip in self.audio_clips[:]:
            if audio_clip.player.unique_id == player.unique_id:
                audio_clip.Stop()
