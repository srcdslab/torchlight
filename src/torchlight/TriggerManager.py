import os
from collections import OrderedDict

from torchlight.Config import Config, ConfigFile


class TriggerManager(ConfigFile):
    def __init__(
        self,
        config_folder: str,
        config: Config,
        config_filename: str = "triggers.json",
    ) -> None:
        super().__init__(config_folder, config_filename)
        self.config = config
        self.triggers_dict: OrderedDict = OrderedDict()
        self.voice_triggers: dict[str, dict[str, str | list[str] | dict[str, float]]] = {}
        self.sound_path = self.config.config.get("Sounds", {}).get("Path", "sounds")

    def Load(self) -> None:
        self.logger.info(f"Loading triggers from {self.config_filepath}")

        voice_server_params = self.config.config.get("VoiceServer", {}).get("AudioParams", {})
        default_parameters = {
            "Volume": float(voice_server_params.get("Volume", {}).get("Default", 1.0)),
            "Speed": float(voice_server_params.get("Speed", {}).get("Default", 1.0)),
            "Pitch": float(voice_server_params.get("Pitch", {}).get("Default", 1.0)),
        }

        self.triggers_dict = self.load_json(ordered=True)
        for line in self.triggers_dict:
            for trigger in line["names"]:
                config_sounds = line["sound"]
                parameters: dict[str, float] | None = None
                if "parameters" in line:
                    parameters = line["parameters"]

                if parameters:
                    for key in ["Volume", "Speed", "Pitch"]:
                        if key not in parameters:
                            parameters[key] = default_parameters[key]
                        else:
                            parameters[key] = float(parameters[key])

                self.voice_triggers[trigger] = {
                    "sounds": config_sounds,
                    "parameters": parameters if parameters else default_parameters,
                }

                sounds: list[str] = []
                if isinstance(config_sounds, str):
                    sounds.append(config_sounds)
                elif isinstance(config_sounds, list):
                    sounds.extend(config_sounds)

                for sound in sounds:
                    sound_path = os.path.abspath(os.path.join(self.sound_path, sound))
                    if not os.path.exists(sound_path):
                        self.logger.warning(f"Sound path {sound_path} does not exist")
