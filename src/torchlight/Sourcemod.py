import copy
from collections import OrderedDict
from dataclasses import dataclass

from torchlight.Config import Config, ConfigFile


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


class SourcemodConfig(ConfigFile):
    def __init__(
        self,
        config_folder: str,
        config: Config,
        config_filename: str = "flags.json",
    ) -> None:
        super().__init__(config_folder, config_filename)
        self.config = config
        self.sm_flags: OrderedDict = OrderedDict()
        self.sm_groups: list[SourcemodGroup] = []

    def Load(self) -> None:
        self.sm_flags = self.load_json(ordered=True)
        self.sm_groups.clear()
        for sm_group in self.config["SourcemodGroups"]:
            self.sm_groups.append(
                SourcemodGroup(
                    name=sm_group["name"],
                    level=sm_group["level"],
                    flags=sm_group["flags"],
                )
            )

    def flagbits_to_flags(self, *, flagbits: int) -> list[str]:
        flags: list[str] = []
        for index, sm_flag in enumerate(self.sm_flags.values()):
            if flagbits & (1 << index):
                flags.append(sm_flag["value"])
        return flags

    def get_sourcemod_groups_by_flags(self, *, flagbits: int) -> list[SourcemodGroup]:
        groups = []
        flags = self.flagbits_to_flags(flagbits=flagbits)
        for sm_group in self.sm_groups:
            if sm_group.flags:
                for flag in flags:
                    if flag in sm_group.flags and sm_group not in groups:
                        groups.append(copy.deepcopy(sm_group))
            else:
                groups.append(copy.deepcopy(sm_group))
        return groups

    def get_highest_group_level(self, *, sm_groups: list[SourcemodGroup]) -> SourcemodGroup | None:
        highest_group: SourcemodGroup | None = None
        for sm_group in sm_groups:
            if highest_group is None or sm_group.level > highest_group.level:
                highest_group = sm_group
        return highest_group
