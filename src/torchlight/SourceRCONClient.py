import asyncio
import logging
import socket
import struct
import sys
from typing import Any, Awaitable, Generator

from torchlight.CommandHandler import CommandHandler
from torchlight.Config import ConfigAccess
from torchlight.Player import Player


class SourceRCONClient:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        Socket: socket.socket,
        Name: Any,
        ServerPassword: str,
        command_handler: CommandHandler,
    ):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.loop: asyncio.AbstractEventLoop = loop
        self.command_handler = command_handler
        self._sock: socket.socket = Socket
        self.Name: Any = Name
        self.ServerPassword: str = ServerPassword
        self.Authenticated = False

    def send(self, data: bytes) -> Awaitable:
        return self.loop.sock_sendall(self._sock, data)

    @asyncio.coroutine
    def _peer_loop(self) -> Generator:
        while True:
            Data = yield from self.loop.sock_recv(self._sock, 1024)
            if Data == b'':
                break

            while Data:
                p_size = struct.unpack("<l", Data[:4])[0]
                if len(Data) < p_size + 4:
                    break
                self.ParsePacket(Data[: p_size + 4])
                Data = Data[p_size + 4 :]

    def p_send(self, p_id: int, p_type: int, p_body: str) -> None:
        Data = (
            struct.pack('<l', p_id)
            + struct.pack('<l', p_type)
            + p_body.encode("UTF-8")
            + b'\x00\x00'
        )
        self.send(struct.pack('<l', len(Data)) + Data)

    def ParsePacket(self, DataRaw: bytes) -> None:
        p_size, p_id, p_type = struct.unpack('<lll', DataRaw[:12])
        Data: str = (
            DataRaw[12 : p_size + 2]
            .decode(encoding="UTF-8", errors="ignore")
            .split('\x00')[0]
        )

        if not self.Authenticated:
            if p_type == 3:
                if Data == self.ServerPassword:
                    self.Authenticated = True
                    self.Logger.info(
                        sys._getframe().f_code.co_name
                        + " Connection authenticated from {0}".format(self.Name)
                    )
                    self.p_send(p_id, 0, '')
                    self.p_send(p_id, 2, '')
                    self.p_send(p_id, 0, "Welcome to torchlight! - Authenticated!\n")
                else:
                    self.Logger.info(
                        sys._getframe().f_code.co_name
                        + " Connection denied from {0}".format(self.Name)
                    )
                    self.p_send(p_id, 0, '')
                    self.p_send(-1, 2, '')
                    self._sock.close()
        else:
            if p_type == 2:
                if Data:
                    Data = Data.strip('"')
                    self.Logger.info(
                        sys._getframe().f_code.co_name + " Exec: \"{0}\"".format(Data)
                    )
                    player = Player(
                        0,
                        0,
                        "[CONSOLE]",
                        "127.0.0.1",
                        "CONSOLE",
                    )
                    player.access = ConfigAccess(
                        name="CONSOLE", level=9001, uniqueid="CONSOLE"
                    )
                    player.Storage = dict(
                        {
                            "Audio": {
                                "Uses": 0,
                                "LastUse": 0.0,
                                "LastUseLength": 0.0,
                                "TimeUsed": 0.0,
                            }
                        }
                    )
                    asyncio.Task(self.command_handler.HandleCommand(Data, player))
                    # self.p_send(p_id, 0, self._server.torchlight.GetLine())
