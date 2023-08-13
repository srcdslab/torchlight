import json
import logging
from collections import OrderedDict

from torchlight.Config import ConfigAccess
from torchlight.Player import Player


class AccessManager:
    def __init__(
        self, config_folder: str, config_filename: str = "access.json"
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = config_folder
        self.config_filename = config_filename
        self.config_filepath = f"{config_folder}/{config_filename}"
        self.access_dict: OrderedDict = OrderedDict()
        self.config_access_list: dict[str, ConfigAccess] = {}

    def Load(self) -> None:
        self.logger.info(f"Loading access from {self.config_filepath}")

        with open(self.config_filepath) as fp:
            self.access_dict = json.load(fp, object_pairs_hook=OrderedDict)
            for unique_id, access in self.access_dict.items():
                self.config_access_list[unique_id] = ConfigAccess(
                    name=access["name"],
                    level=access["level"],
                    uniqueid=unique_id,
                )

        self.logger.info(f"Loaded {self.config_access_list}")

    def Save(self) -> None:
        self.logger.info(f"Saving access to {self.config_filepath}")

        for unique_id, access in self.config_access_list.items():
            self.access_dict[unique_id] = {
                "name": access.name,
                "level": access.level,
            }

        self.access_dict = OrderedDict(
            sorted(
                self.access_dict.items(),
                key=lambda x: x[1]["level"],
                reverse=True,
            )
        )

        with open(self.config_filepath, "w") as fp:
            json.dump(self.access_dict, fp, indent="\t")

    def get_access(self, player: Player) -> ConfigAccess:
        for unique_id, access in self.config_access_list.items():
            if unique_id == player.unique_id:
                return access
        return player.access
