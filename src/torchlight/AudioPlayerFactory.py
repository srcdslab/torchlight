import logging
from enum import Enum

from torchlight.FFmpegAudioPlayer import FFmpegAudioPlayer
from torchlight.FFmpegAudioPlayerFactory import FFmpegAudioPlayerFactory
from torchlight.Torchlight import Torchlight


class AudioPlayerType(Enum):
    AUDIOPLAYER_FFMPEG = 1


class AudioPlayerFactory:
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        self.ffmpeg_audio_player_factory = FFmpegAudioPlayerFactory()

    def __del__(self) -> None:
        self.logger.info("~AudioPlayerFactory()")

    def NewPlayer(
        self, _type: AudioPlayerType, torchlight: Torchlight
    ) -> FFmpegAudioPlayer:
        if _type == AudioPlayerType.AUDIOPLAYER_FFMPEG:
            return self.ffmpeg_audio_player_factory.NewPlayer(torchlight)
        return self.ffmpeg_audio_player_factory.NewPlayer(torchlight)
