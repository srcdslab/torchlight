#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import logging
from collections import OrderedDict
from typing import Any, Iterator, Optional

from torchlight.Config import ConfigAccess
from torchlight.Player import Player


class AccessManager:
    def __init__(
        self, config_folder: str, config_filename: str = "access.json"
    ) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = config_folder
        self.config_filename = config_filename
        self.config_filepath = f"{config_folder}/{config_filename}"
        self.AccessDict: OrderedDict = OrderedDict()

    def Load(self) -> None:
        self.Logger.info("Loading access from {0}".format(self.config_filepath))

        with open(self.config_filepath, "r") as fp:
            self.AccessDict = json.load(fp, object_pairs_hook=OrderedDict)

    def Save(self) -> None:
        self.Logger.info("Saving access to {0}".format(self.config_filepath))

        self.AccessDict = OrderedDict(
            sorted(self.AccessDict.items(), key=lambda x: x[1]["level"], reverse=True)
        )

        with open(self.config_filepath, "w") as fp:
            json.dump(self.AccessDict, fp, indent="\t")

    def get_access(self, player: Player) -> ConfigAccess:
        access_dict: Optional[OrderedDict] = self[player.UniqueID]
        access: ConfigAccess = player.access
        if access_dict is not None:
            access.name = access_dict["name"]
            access.level = access_dict["level"]
        return access

    def __len__(self) -> int:
        return len(self.AccessDict)

    def __getitem__(self, key: str) -> Optional[Any]:
        if key in self.AccessDict:
            return self.AccessDict[key]
        return None

    def __setitem__(self, key: str, value: Any) -> None:
        self.AccessDict[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self.AccessDict:
            del self.AccessDict[key]

    def __iter__(self) -> Iterator:
        return self.AccessDict.items().__iter__()
