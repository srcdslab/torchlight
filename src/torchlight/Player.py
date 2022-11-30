#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict

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
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Index = index
        self.UserID = userid
        self.UniqueID = uniqueid
        self.Address = address
        self.Name = name
        self.access: ConfigAccess = ConfigAccess(
            name=self.Name, level=0, uniqueid=self.UniqueID
        )
        self.Admin = Admin()
        self.Storage: Dict = dict()
        self.Active = False
        self.ChatCooldown = 0

    def OnConnect(self, storage: Dict, access: ConfigAccess) -> None:
        self.Storage = storage

        if not "Audio" in self.Storage:
            self.Storage["Audio"] = dict(
                {"Uses": 0, "LastUse": 0.0, "LastUseLength": 0.0, "TimeUsed": 0.0}
            )

        self.access = access

    def OnActivate(self) -> None:
        self.Active = True

    def OnClientPostAdminCheck(self, flag_bits: int, config: Config) -> None:
        self.Admin._FlagBits = flag_bits
        self.Logger.info(
            "#{0} \"{1}\"({2}) FlagBits: {3}".format(
                self.UserID, self.Name, self.UniqueID, self.Admin._FlagBits
            )
        )
        if not self.access:
            if self.Admin.RCON() or self.Admin.Root():
                self.access = ConfigAccess(
                    level=config["AccessLevel"]["Root"],
                    name="SAdmin",
                    uniqueid=self.UniqueID,
                )
            elif self.Admin.Ban():
                self.access = ConfigAccess(
                    level=config["AccessLevel"]["Admin"],
                    name="Admin",
                    uniqueid=self.UniqueID,
                )
            elif self.Admin.Generic():
                self.access = ConfigAccess(
                    level=config["AccessLevel"]["DonatedAdmin"],
                    name="DAdmin",
                    uniqueid=self.UniqueID,
                )
            elif self.Admin.Custom1():
                self.access = ConfigAccess(
                    level=config["AccessLevel"]["VIP"],
                    name="VIP",
                    uniqueid=self.UniqueID,
                )

        if "DefaultLevel" in config.config:
            if self.access and self.access.level < config["DefaultLevel"]:
                self.access = ConfigAccess(
                    level=config["DefaultLevel"],
                    name="Default",
                    uniqueid=self.UniqueID,
                )

    def OnInfo(self, name: str) -> None:
        self.Name = name

    def OnDisconnect(self, message: str) -> None:
        self.Active = False
        self.Storage = dict()
