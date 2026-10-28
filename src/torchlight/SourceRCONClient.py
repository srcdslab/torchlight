import asyncio
import hmac
import logging
import socket
import struct
import sys
from collections.abc import Callable
from typing import Any

from torchlight.CommandHandler import CommandHandler
from torchlight.PlayerManager import PlayerManager
from torchlight.Utils import Utils

# Source RCON packet types.
SERVERDATA_RESPONSE_VALUE = 0
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_AUTH = 3

# A packet is: size (int32), then id (int32), type (int32), body, NUL, NUL; size excludes its own 4 bytes.
PACKET_SIZE_FIELD = 4
PACKET_MIN_SIZE = 10
PACKET_MAX_SIZE = 4096

RECV_CHUNK_SIZE = 4096
# Unauthenticated peers must authenticate within this delay, so idle sockets cannot hold a peer slot forever.
AUTH_TIMEOUT = 30.0


class SourceRCONClient:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        sock: socket.socket,
        name: Any,
        server_password: str,
        get_command_handler: Callable[[], CommandHandler],
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop: asyncio.AbstractEventLoop = loop
        # Resolved at dispatch time: TorchlightHandler.Init() replaces its CommandHandler on every
        # SourceMod reconnect, and a captured instance would run commands against the dead client.
        self.get_command_handler = get_command_handler
        self._sock: socket.socket = sock
        self.name: Any = name
        self.server_password: bytes = server_password.encode("UTF-8")
        self.authenticated = False
        self._buffer = bytearray()
        self._closed = False

    async def send(self, data: bytes) -> None:
        await self.loop.sock_sendall(self._sock, data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._buffer.clear()
        self._sock.close()

    async def _recv(self) -> bytes:
        if self.authenticated:
            return await self.loop.sock_recv(self._sock, RECV_CHUNK_SIZE)
        try:
            return await asyncio.wait_for(self.loop.sock_recv(self._sock, RECV_CHUNK_SIZE), AUTH_TIMEOUT)
        except TimeoutError:
            self.logger.info(sys._getframe().f_code.co_name + f" Authentication timeout from {self.name}")
            return b""

    # @profile
    async def _peer_loop(self) -> None:
        while not self._closed:
            data = await self._recv()
            if data == b"":
                return

            self._buffer += data
            # Only complete packets are consumed; a partial one stays buffered until the rest arrives.
            while len(self._buffer) >= PACKET_SIZE_FIELD:
                p_size = int.from_bytes(self._buffer[:PACKET_SIZE_FIELD], "little", signed=True)
                if p_size < PACKET_MIN_SIZE or p_size > PACKET_MAX_SIZE:
                    self.logger.warning(
                        sys._getframe().f_code.co_name + f" Invalid packet size {p_size} from {self.name}, closing"
                    )
                    return

                p_end = PACKET_SIZE_FIELD + p_size
                if len(self._buffer) < p_end:
                    break

                packet = bytes(self._buffer[:p_end])
                del self._buffer[:p_end]
                if not await self.ParsePacket(packet):
                    return

    # @profile
    async def p_send(self, p_id: int, p_type: int, p_body: str) -> None:
        data = struct.pack("<ll", p_id, p_type) + p_body.encode("UTF-8") + b"\x00\x00"
        await self.send(struct.pack("<l", len(data)) + data)

    # @profile
    async def ParsePacket(self, data_raw: bytes) -> bool:
        """Handles one complete packet. Returns False when the connection must be closed."""
        p_size, p_id, p_type = struct.unpack("<lll", data_raw[:12])
        body: bytes = data_raw[12 : PACKET_SIZE_FIELD + p_size - 2].split(b"\x00")[0]

        if not self.authenticated:
            if p_type != SERVERDATA_AUTH:
                return True

            # An empty configured password disables RCON instead of accepting an empty password.
            if self.server_password and hmac.compare_digest(body, self.server_password):
                self.authenticated = True
                self.logger.info(sys._getframe().f_code.co_name + f" Connection authenticated from {self.name}")
                await self.p_send(p_id, SERVERDATA_RESPONSE_VALUE, "")
                await self.p_send(p_id, SERVERDATA_AUTH_RESPONSE, "")
                await self.p_send(p_id, SERVERDATA_RESPONSE_VALUE, "Welcome to torchlight! - Authenticated!\n")
                return True

            self.logger.info(sys._getframe().f_code.co_name + f" Connection denied from {self.name}")
            await self.p_send(p_id, SERVERDATA_RESPONSE_VALUE, "")
            await self.p_send(-1, SERVERDATA_AUTH_RESPONSE, "")
            return False

        if p_type == SERVERDATA_EXECCOMMAND:
            data = body.decode(encoding="UTF-8", errors="ignore").strip('"')
            if data:
                self.logger.info(sys._getframe().f_code.co_name + f' Exec: "{data}"')

                player = PlayerManager.create_console_player()
                Utils.FireAndForget(self.get_command_handler().HandleCommand(data, player), self.logger)
            # Command output is not captured; an empty response lets clients waiting on the id move on.
            await self.p_send(p_id, SERVERDATA_RESPONSE_VALUE, "")

        return True
