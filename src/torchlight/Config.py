import json
import logging
import os
import sys
from collections import OrderedDict
from typing import Any


class ConfigFile:
    """Resolves a config file path under the config folder and parses it as JSON."""

    def __init__(
        self,
        config_folder: str,
        config_filename: str,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = os.path.abspath(config_folder)
        self.config_filename = config_filename
        self.config_filepath = os.path.abspath(os.path.join(config_folder, config_filename))

    def load_json(self, *, ordered: bool = False) -> Any:
        with open(self.config_filepath) as fp:
            if ordered:
                return json.load(fp, object_pairs_hook=OrderedDict)
            return json.load(fp)


class Config(ConfigFile):
    def __init__(
        self,
        config_folder: str,
        config_filename: str = "config.json",
    ) -> None:
        super().__init__(config_folder, config_filename)
        self.config: dict[str, Any] = {}

    def load(self) -> int:
        try:
            self.config = self.load_json()
        except ValueError as e:
            self.logger.error(sys._getframe().f_code.co_name + " " + str(e))
            return 1
        return 0

    def __getitem__(self, key: str) -> Any:
        if key in self.config:
            return self.config[key]
        raise Exception(f"Key {key} not found in config")
