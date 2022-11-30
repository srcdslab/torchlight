import logging
import sys

from torchlight.FFmpegAudioPlayer import FFmpegAudioPlayer
from torchlight.Torchlight import Torchlight


class FFmpegAudioPlayerFactory:
    def __init__(self) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)

    def __del__(self) -> None:
        self.Logger.info("~FFmpegAudioPlayerFactory()")
        self.Quit()

    def NewPlayer(self, torchlight: Torchlight) -> FFmpegAudioPlayer:
        self.Logger.debug(sys._getframe().f_code.co_name)
        Player = FFmpegAudioPlayer(torchlight)
        return Player

    def Quit(self) -> None:
        self.Logger.info("FFmpegAudioPlayerFactory->Quit()")
