#!/usr/bin/python3
import logging

from torchlight.Admin import Admin
from torchlight.Config import Config, ConfigAccess


class Player:
    def __init__(
        self,
        index: int,
        userid: int,
        uniqueid: str,
        address: str,
        name: str,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.index = index
        self.user_id = userid
        self.unique_id = uniqueid
        self.address = address
        self.name = name
        self.access: ConfigAccess = ConfigAccess(
            name=self.name, level=0, uniqueid=self.unique_id
        )
        self.admin = Admin()
        self.storage: dict = {}
        self.active = False
        self.chat_cooldown = 0

    def OnConnect(self) -> None:
        if "Audio" not in self.storage:
            self.storage["Audio"] = dict(
                {"Uses": 0, "LastUse": 0.0, "LastUseLength": 0.0, "TimeUsed": 0.0}
            )

    def OnActivate(self) -> None:
        self.active = True

    def OnClientPostAdminCheck(self, flag_bits: int, config: Config) -> None:
        self.admin._flag_bits = flag_bits
        self.logger.info(
            '#{} "{}"({}) FlagBits: {}'.format(
                self.user_id, self.name, self.unique_id, self.admin._flag_bits
            )
        )

        player_access = ConfigAccess(
            name="Player",
            level=config["AccessLevel"]["Player"],
            uniqueid=self.unique_id,
        )

        if self.admin.RCON() or self.admin.Root():
            player_access = ConfigAccess(
                level=config["AccessLevel"]["Root"],
                name="SAdmin",
                uniqueid=self.unique_id,
            )
        elif self.admin.Ban():
            player_access = ConfigAccess(
                level=config["AccessLevel"]["Admin"],
                name="Admin",
                uniqueid=self.unique_id,
            )
        elif self.admin.Generic():
            player_access = ConfigAccess(
                level=config["AccessLevel"]["DonatedAdmin"],
                name="DAdmin",
                uniqueid=self.unique_id,
            )
        elif self.admin.Custom1():
            player_access = ConfigAccess(
                level=config["AccessLevel"]["VIP"],
                name="VIP",
                uniqueid=self.unique_id,
            )

        if player_access is not None and self.access.level < player_access.level:
            self.access = player_access

    def OnInfo(self, name: str) -> None:
        self.name = name

    def OnDisconnect(self, message: str) -> None:
        self.active = False
        self.storage = {}
