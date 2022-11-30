#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import logging
from collections import OrderedDict
from typing import Any, Iterator, Optional


class AccessManager:
    ACCESS_FILE = "config/access.json"

    def __init__(self) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.AccessDict: OrderedDict = OrderedDict()

    def Load(self) -> None:
        self.Logger.info("Loading access from {0}".format(self.ACCESS_FILE))

        with open(self.ACCESS_FILE, "r") as fp:
            self.AccessDict = json.load(fp, object_pairs_hook=OrderedDict)

    def Save(self) -> None:
        self.Logger.info("Saving access to {0}".format(self.ACCESS_FILE))

        self.AccessDict = OrderedDict(
            sorted(self.AccessDict.items(), key=lambda x: x[1]["level"], reverse=True)
        )

        with open(self.ACCESS_FILE, "w") as fp:
            json.dump(self.AccessDict, fp, indent='\t')

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
