class Clients:
    MAXPLAYERS = 65
    MAX_NAME_LENGTH = 128
    MAX_AUTHID_LENGTH = 64


class AdminFlagBits:
    ADMFLAG_RESERVATION = 1 << 0
    ADMFLAG_GENERIC = 1 << 1
    ADMFLAG_KICK = 1 << 2
    ADMFLAG_BAN = 1 << 3
    ADMFLAG_UNBAN = 1 << 4
    ADMFLAG_SLAY = 1 << 5
    ADMFLAG_CHANGEMAP = 1 << 6
    ADMFLAG_CONVARS = 1 << 7
    ADMFLAG_CONFIG = 1 << 8
    ADMFLAG_CHAT = 1 << 9
    ADMFLAG_VOTE = 1 << 10
    ADMFLAG_PASSWORD = 1 << 11
    ADMFLAG_RCON = 1 << 12
    ADMFLAG_CHEATS = 1 << 13
    ADMFLAG_ROOT = 1 << 14
    ADMFLAG_CUSTOM1 = 1 << 15
    ADMFLAG_CUSTOM2 = 1 << 16
    ADMFLAG_CUSTOM3 = 1 << 17
    ADMFLAG_CUSTOM4 = 1 << 18
    ADMFLAG_CUSTOM5 = 1 << 19
    ADMFLAG_CUSTOM6 = 1 << 20
