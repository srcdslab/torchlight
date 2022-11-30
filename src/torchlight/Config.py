#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import logging
import sys
from typing import Any, Dict, Optional


class Config:
    def __init__(self) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Config: Dict[str, Any] = dict()
        if len(sys.argv) >= 2:
            self.ConfigPath = sys.argv[1]
        else:
            self.ConfigPath = "config/config.json"
        self.Load()

    def Load(self) -> int:
        try:
            with open(self.ConfigPath, "r") as fp:
                self.Config = json.load(fp)
        except ValueError as e:
            self.Logger.error(sys._getframe().f_code.co_name + ' ' + str(e))
            return 1
        return 0

    def __getitem__(self, key: str) -> Optional[Any]:
        if key in self.Config:
            return self.Config[key]
        return None
