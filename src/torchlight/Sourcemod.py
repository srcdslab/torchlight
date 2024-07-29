import json
import logging
import os
import sys
from collections import OrderedDict
from dataclasses import dataclass

from torchlight.Config import Config


@dataclass
class SourcemodGroup:
    name: str
    level: int
    flags: list[str]


@dataclass
class SourcemodAdmin:
    name: str
    unique_id: str
    flag_bits: int
    groups: list[SourcemodGroup]
    level: int


class SourcemodConfig:
    def __init__(
        self,
        config_folder: str,
        config: Config,
        config_filename: str = "flags.json",
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.config_folder = os.path.abspath(config_folder)
        self.config_filename = config_filename
        self.config_filepath = os.path.abspath(
            os.path.join(config_folder, config_filename)
        )
        self.sm_flags: OrderedDict = OrderedDict()
        self.sm_groups: list[SourcemodGroup] = []

    def Load(self) -> int:
        try:
            with open(self.config_filepath) as fp:
                self.sm_flags = json.load(fp, object_pairs_hook=OrderedDict)
        except ValueError as e:
            self.logger.error(sys._getframe().f_code.co_name + " " + str(e))
            return 1
        self.sm_groups.clear()
        for sm_group in self.config["SourcemodGroups"]:
            self.sm_groups.append(
                SourcemodGroup(
                    name=sm_group["name"],
                    level=sm_group["level"],
                    flags=sm_group["flags"],
                )
            )
        return 0

    def flagbits_to_flags(self, *, flagbits: int) -> list[str]:
        flags: list[str] = []
        for index, sm_flag in enumerate(self.sm_flags.values()):
            if flagbits & (1 << index):
                flags.append(sm_flag["value"])
        return flags

    def get_sourcemod_groups_by_flags(
        self, *, flagbits: int
    ) -> list[SourcemodGroup]:
        groups = []
        flags = self.flagbits_to_flags(flagbits=flagbits)
        for sm_group in self.sm_groups:
            if sm_group.flags:
                for flag in flags:
                    if flag in sm_group.flags and sm_group not in groups:
                        groups.append(sm_group)
            else:
                groups.append(sm_group)
        return groups

    def get_highest_group_level(
        self, *, sm_groups: list[SourcemodGroup]
    ) -> (SourcemodGroup | None):
        highest_group: SourcemodGroup | None = None
        for sm_group in sm_groups:
            if highest_group is None or sm_group.level > highest_group.level:
                highest_group = sm_group
        return highest_group
