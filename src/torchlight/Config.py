import json
import logging
import os
import sys
from typing import Any


class Config:
    def __init__(
        self,
        config_folder: str,
        config_filename: str = "config.json",
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = os.path.abspath(config_folder)
        self.config_filename = config_filename
        self.config_filepath = os.path.abspath(
            os.path.join(config_folder, config_filename)
        )
        self.config: dict[str, Any] = {}

    def load(self) -> int:
        try:
            with open(self.config_filepath) as fp:
                self.config = json.load(fp)
        except ValueError as e:
            self.logger.error(sys._getframe().f_code.co_name + " " + str(e))
            return 1
        return 0

    def __getitem__(self, key: str) -> Any:
        if key in self.config:
            return self.config[key]
        raise Exception(f"Key {key} not found in config")
