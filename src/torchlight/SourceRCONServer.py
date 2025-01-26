import asyncio
import logging
import socket
import sys
from typing import Any

from torchlight.SourceRCONClient import SourceRCONClient
from torchlight.TorchlightHandler import TorchlightHandler


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
        self.password = self.rcon_config["Password"]

    def Remove(self, peer: SourceRCONClient) -> None:
        self.logger.info(sys._getframe().f_code.co_name + f" Peer {peer.name} disconnected!")
        self.peers.remove(peer)

    async def _server(self) -> None:
        while True:
            peer_socket: socket.socket
            peer_name: Any
            peer_socket, peer_name = await self.loop.sock_accept(self._serv_sock)
            peer_socket.setblocking(False)
            peer = SourceRCONClient(
                self.loop,
                peer_socket,
                peer_name,
                self.password,
                self.torchlight_handler.command_handler,
            )
            asyncio.Task(self._peer_handler(peer))
            self.peers.append(peer)
            self.logger.info(sys._getframe().f_code.co_name + f" Peer {peer.name} connected!")

    async def _peer_handler(self, peer: SourceRCONClient) -> None:
        try:
            await peer._peer_loop()
        except OSError:
            pass
        finally:
            self.Remove(peer)
