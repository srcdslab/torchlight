import asyncio
import logging
import socket
import struct
import sys
from collections.abc import Awaitable
from typing import Any

from torchlight.CommandHandler import CommandHandler
from torchlight.Player import Player
from torchlight.Sourcemod import SourcemodAdmin


class SourceRCONClient:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        sock: socket.socket,
        name: Any,
        server_password: str,
        command_handler: CommandHandler,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop: asyncio.AbstractEventLoop = loop
        self.command_handler = command_handler
        self._sock: socket.socket = sock
        self.name: Any = name
        self.server_password: str = server_password
        self.authenticated = False

    def send(self, data: bytes) -> Awaitable:
        return self.loop.sock_sendall(self._sock, data)

    # @profile
    async def _peer_loop(self) -> None:
        while True:
            data = await self.loop.sock_recv(self._sock, 1024)
            if data == b"":
                break

            while data:
                p_size = struct.unpack("<l", data[:4])[0]
                if len(data) < p_size + 4:
                    break
                self.ParsePacket(data[: p_size + 4])
                data = data[p_size + 4 :]

    # @profile
    def p_send(self, p_id: int, p_type: int, p_body: str) -> None:
        data = struct.pack("<l", p_id) + struct.pack("<l", p_type) + p_body.encode("UTF-8") + b"\x00\x00"
        self.send(struct.pack("<l", len(data)) + data)

    # @profile
    def ParsePacket(self, data_raw: bytes) -> None:
        p_size, p_id, p_type = struct.unpack("<lll", data_raw[:12])
        data: str = data_raw[12 : p_size + 2].decode(encoding="UTF-8", errors="ignore").split("\x00")[0]

        if not self.authenticated:
            if p_type == 3:
                if data == self.server_password:
                    self.authenticated = True
                    self.logger.info(sys._getframe().f_code.co_name + f" Connection authenticated from {self.name}")
                    self.p_send(p_id, 0, "")
                    self.p_send(p_id, 2, "")
                    self.p_send(p_id, 0, "Welcome to torchlight! - Authenticated!\n")
                else:
                    self.logger.info(sys._getframe().f_code.co_name + f" Connection denied from {self.name}")
                    self.p_send(p_id, 0, "")
                    self.p_send(-1, 2, "")
                    self._sock.close()
        else:
            if p_type == 2:
                if data:
                    data = data.strip('"')
                    self.logger.info(sys._getframe().f_code.co_name + f' Exec: "{data}"')
                    player = Player(
                        0,
                        0,
                        "[CONSOLE]",
                        "127.0.0.1",
                        "CONSOLE",
                    )
                    player.admin = SourcemodAdmin(
                        name="CONSOLE",
                        unique_id=player.unique_id,
                        level=100,
                        flag_bits=0,
                        groups=[],
                    )
                    player.storage = dict(
                        {
                            "Audio": {
                                "Uses": 0,
                                "LastUse": 0.0,
                                "LastUseLength": 0.0,
                                "TimeUsed": 0.0,
                            }
                        }
                    )
                    asyncio.Task(self.command_handler.HandleCommand(data, player))
                    # self.p_send(p_id, 0, self._server.torchlight.GetLine())
