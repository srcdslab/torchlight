import json
import logging
import os
from collections import OrderedDict

from torchlight.Config import Config


class TriggerManager:
    def __init__(
        self,
        config_folder: str,
        config: Config,
        config_filename: str = "triggers.json",
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.config_folder = os.path.abspath(config_folder)
        self.config_filename = config_filename
        self.config_filepath = os.path.abspath(
            os.path.join(config_folder, config_filename)
        )
        self.triggers_dict: OrderedDict = OrderedDict()
        self.voice_triggers: dict[str, str | list[str]] = {}
        self.sound_path = self.config.config.get("Sounds", {}).get(
            "Path", "sounds"
        )

    def Load(self) -> None:
        self.logger.info(f"Loading triggers from {self.config_filepath}")

        with open(self.config_filepath) as fp:
            self.triggers_dict = json.load(fp, object_pairs_hook=OrderedDict)
            for line in self.triggers_dict:
                for trigger in line["names"]:
                    config_sounds = line["sound"]
                    self.voice_triggers[trigger] = config_sounds

                    sounds: list[str] = []
                    if isinstance(config_sounds, str):
                        sounds.append(config_sounds)
                    elif isinstance(config_sounds, list):
                        sounds.extend(config_sounds)

                    for sound in sounds:
                        sound_path = os.path.abspath(
                            os.path.join(self.sound_path, sound)
                        )
                        if not os.path.exists(sound_path):
                            self.logger.warn(
                                f"Sound path {sound_path} does not exist"
                            )
