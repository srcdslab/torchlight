import logging

from torchlight.Sourcemod import SourcemodAdmin, SourcemodConfig


class Player:
    def __init__(
        self,
        index: int,
        userid: int,
        unique_id: str,
        address: str,
        name: str,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.index = index
        self.user_id = userid
        self.unique_id = unique_id
        self.address = address
        self.name = name
        self.admin = SourcemodAdmin(
            name=self.name,
            unique_id=self.unique_id,
            flag_bits=0,
            groups=[],
            level=0,
        )
        self.storage: dict = {}
        self.active = False
        self.chat_cooldown = 0

    def OnConnect(self) -> None:
        if "Audio" not in self.storage:
            self.storage["Audio"] = dict(
                {
                    "Uses": 0,
                    "LastUse": 0.0,
                    "LastUseLength": 0.0,
                    "TimeUsed": 0.0,
                }
            )

    def OnActivate(self) -> None:
        self.active = True

    def OnClientPostAdminCheck(
        self,
        *,
        flag_bits: int,
        sourcemod_config: SourcemodConfig,
    ) -> None:
        self.admin.flag_bits = flag_bits
        self.admin.groups = sourcemod_config.get_sourcemod_groups_by_flags(
            flagbits=flag_bits
        )

        self.logger.info(
            f'#{self.user_id} "{self.name}"({self.unique_id}) FlagBits: {flag_bits} Groups: {self.admin.groups}'
        )

        group = sourcemod_config.get_highest_group_level(
            sm_groups=self.admin.groups
        )
        if group is not None and group.level > self.admin.level:
            self.admin.level = group.level

    def OnInfo(self, name: str) -> None:
        self.name = name

    def OnDisconnect(self, message: str) -> None:
        self.active = False
        self.storage = {}
