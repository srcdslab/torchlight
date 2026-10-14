import asyncio
import logging
import socket
import sys
from typing import Any

from torchlight.CommandHandler import CommandHandler
from torchlight.SourceRCONClient import SourceRCONClient
from torchlight.TorchlightHandler import TorchlightHandler
from torchlight.Utils import Utils

# Value shipped in config/config.json; anyone who has read the repository knows it.
SHIPPED_DEFAULT_RCON_CREDENTIAL = "supersecretpassword"
# Connections beyond this are refused, so a flood of sockets cannot grow the peer list without bound.
MAX_PEERS = 16


class SourceRCONServer:
    def __init__(self, rcon_config: dict[str, Any], torchlight_handler: TorchlightHandler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rcon_config = rcon_config
        self.torchlight_handler = torchlight_handler
        self.loop: asyncio.AbstractEventLoop = self.torchlight_handler.loop
        self._serv_sock = socket.socket()
        self._serv_sock.setblocking(False)
        self._serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._serv_sock.bind((self.rcon_config["Host"], self.rcon_config["Port"]))
        self._serv_sock.listen(5)
        self.peers: list[SourceRCONClient] = []
        self.password: str = str(self.rcon_config["Password"] or "")

        if not self.password:
            self.logger.warning("TorchRCON password is empty: RCON authentication is disabled")
        elif self.password == SHIPPED_DEFAULT_RCON_CREDENTIAL:
            self.logger.warning(
                "TorchRCON password is the shipped default: anyone can get console access, change it in config.json"
            )

    def GetCommandHandler(self) -> CommandHandler:
        # Looked up on every command so RCON sessions follow the CommandHandler of the current connection.
        return self.torchlight_handler.command_handler

    def Remove(self, peer: SourceRCONClient) -> None:
        if peer in self.peers:
            self.peers.remove(peer)
            self.logger.info(sys._getframe().f_code.co_name + f" Peer {peer.name} disconnected!")

    async def _server(self) -> None:
        while True:
            peer_socket: socket.socket
            peer_name: Any
            peer_socket, peer_name = await self.loop.sock_accept(self._serv_sock)
            if len(self.peers) >= MAX_PEERS:
                self.logger.warning(
                    sys._getframe().f_code.co_name + f" Peer {peer_name} refused: {MAX_PEERS} peers already connected"
                )
                peer_socket.close()
                continue

            peer_socket.setblocking(False)
            peer = SourceRCONClient(
                self.loop,
                peer_socket,
                peer_name,
                self.password,
                self.GetCommandHandler,
            )
            self.peers.append(peer)
            self.logger.info(sys._getframe().f_code.co_name + f" Peer {peer.name} connected!")
            Utils.FireAndForget(self._peer_handler(peer), self.logger)

    async def _peer_handler(self, peer: SourceRCONClient) -> None:
        try:
            await peer._peer_loop()
        except OSError:
            pass
        finally:
            peer.close()
            self.Remove(peer)
