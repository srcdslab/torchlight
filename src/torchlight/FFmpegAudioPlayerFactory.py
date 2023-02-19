import logging
import sys

from torchlight.FFmpegAudioPlayer import FFmpegAudioPlayer
from torchlight.Torchlight import Torchlight


class FFmpegAudioPlayerFactory:
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def __del__(self) -> None:
        self.logger.info("~FFmpegAudioPlayerFactory()")
        self.Quit()

    def NewPlayer(self, torchlight: Torchlight) -> FFmpegAudioPlayer:
        self.logger.debug(sys._getframe().f_code.co_name)
        ffmpeg_audio_player = FFmpegAudioPlayer(torchlight)
        return ffmpeg_audio_player

    def Quit(self) -> None:
        self.logger.info("FFmpegAudioPlayerFactory->Quit()")
