import copy
import json
import logging
import os
from collections import OrderedDict

from torchlight.Sourcemod import SourcemodAdmin


class AccessManager:
    def __init__(self, config_folder: str, config_filename: str = "admins.json") -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = os.path.abspath(config_folder)
        self.config_filename = config_filename
        self.config_filepath = os.path.abspath(os.path.join(config_folder, config_filename))
        self.access_dict: OrderedDict = OrderedDict()
        self.admins: list[SourcemodAdmin] = []

    def Load(self) -> None:
        self.logger.info(f"Loading access from {self.config_filepath}")

        with open(self.config_filepath) as fp:
            self.access_dict = json.load(fp, object_pairs_hook=OrderedDict)
            self.admins.clear()
            for admin_dict in self.access_dict["admins"]:
                self.admins.append(
                    SourcemodAdmin(
                        name=admin_dict["name"],
                        level=admin_dict["level"],
                        unique_id=admin_dict["unique_id"],
                        flag_bits=0,
                        groups=[],
                    )
                )

        self.logger.info(f"Loaded {self.admins}")

    def Save(self) -> None:
        self.logger.info(f"Saving {len(self.admins)} admin access to {self.config_filepath}")

        for admin in self.admins:
            admin_cfg = {
                "name": admin.name,
                "level": admin.level,
                "unique_id": admin.unique_id,
            }

            index = 0
            while index < len(self.access_dict["admins"]):
                admin_dict = self.access_dict["admins"][index]
                if admin.unique_id == admin_dict["unique_id"]:
                    break
                index += 1

            if index >= len(self.access_dict["admins"]):
                self.access_dict["admins"].append(admin_cfg)
            else:
                self.access_dict["admins"][index] = admin_cfg

        self.access_dict["admins"] = sorted(self.access_dict["admins"], key=lambda x: x["level"], reverse=True)

        with open(self.config_filepath, "w") as fp:
            json.dump(self.access_dict, fp, indent="\t")

    def get_admin(self, *, unique_id: str) -> SourcemodAdmin | None:
        admin_copy: SourcemodAdmin | None = None
        for admin in self.admins:
            if admin.unique_id == unique_id:
                admin_copy = copy.deepcopy(admin)
                break
        return admin_copy

    def set_admin(self, unique_id: str, admin: SourcemodAdmin) -> None:
        admin_copy = copy.deepcopy(admin)
        if self.get_admin(unique_id=unique_id) is None:
            self.admins.append(admin_copy)
        else:
            for index, admin in enumerate(self.admins):
                if admin.unique_id == unique_id:
                    self.admins[index] = admin_copy
