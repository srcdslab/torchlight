from torchlight.Constants import AdminFlagBits


class Admin:
    def __init__(self) -> None:
        self._flag_bits = 0

    def FlagBits(self) -> int:
        return self._flag_bits

    def Reservation(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_RESERVATION

    def Generic(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_GENERIC

    def Kick(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_KICK

    def Ban(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_BAN

    def Unban(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_UNBAN

    def Slay(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_SLAY

    def Changemap(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CHANGEMAP

    def Convars(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CONVARS

    def Config(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CONFIG

    def Chat(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CHAT

    def Vote(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_VOTE

    def Password(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_PASSWORD

    def RCON(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_RCON

    def Cheats(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CHEATS

    def Root(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_ROOT

    def Custom1(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CUSTOM1

    def Custom2(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CUSTOM2

    def Custom3(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CUSTOM3

    def Custom4(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CUSTOM4

    def Custom5(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CUSTOM5

    def Custom6(self) -> int:
        return self._flag_bits & AdminFlagBits.ADMFLAG_CUSTOM6
