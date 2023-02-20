#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import socket
import sys
from typing import Any, Dict, Generator, List

from torchlight.SourceRCONClient import SourceRCONClient
from torchlight.TorchlightHandler import TorchlightHandler


class SourceRCONServer:
    def __init__(
        self, rcon_config: Dict[str, Any], torchlight_handler: TorchlightHandler
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rcon_config = rcon_config
        self.torchlight_handler = torchlight_handler
        self.loop: asyncio.AbstractEventLoop = self.torchlight_handler.loop
        self._serv_sock = socket.socket()
        self._serv_sock.setblocking(False)
        self._serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._serv_sock.bind((self.rcon_config["Host"], self.rcon_config["Port"]))
        self._serv_sock.listen(5)
        self.peers: List[SourceRCONClient] = []
        self.password = self.rcon_config["Password"]

    def Remove(self, peer: SourceRCONClient) -> None:
        self.logger.info(
            sys._getframe().f_code.co_name + " Peer {0} disconnected!".format(peer.name)
        )
        self.peers.remove(peer)

    @asyncio.coroutine
    def _server(self) -> Generator:
        while True:
            peer_socket: socket.socket
            peer_name: Any
            peer_socket, peer_name = yield from self.loop.sock_accept(self._serv_sock)
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
            self.logger.info(
                sys._getframe().f_code.co_name
                + " Peer {0} connected!".format(peer.name)
            )

    @asyncio.coroutine
    def _peer_handler(self, peer: SourceRCONClient) -> Generator:
        try:
            yield from peer._peer_loop()
        except IOError:
            pass
        finally:
            self.Remove(peer)
