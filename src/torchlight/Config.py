#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ConfigAccess:
    name: str
    level: int
    uniqueid: str


class Config:
    def __init__(
        self, config_folder: str, config_filename: str = "config.json"
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = config_folder
        self.config_filename = config_filename
        self.config_filepath = f"{config_folder}/{config_filename}"
        self.config: Dict[str, Any] = dict()
        self.Load()

    def Load(self) -> int:
        try:
            with open(self.config_filepath, "r") as fp:
                self.config = json.load(fp)
        except ValueError as e:
            self.logger.error(sys._getframe().f_code.co_name + " " + str(e))
            return 1
        return 0

    def __getitem__(self, key: str) -> Any:
        if key in self.config:
            return self.config[key]
        raise Exception(f"Key {key} not found in config")
