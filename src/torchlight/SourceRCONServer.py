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
        self, RCONConfig: Dict[str, Any], torchlight_handler: TorchlightHandler
    ):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.RCONConfig = RCONConfig
        self.torchlight_handler = torchlight_handler
        self.loop: asyncio.AbstractEventLoop = self.torchlight_handler.loop
        self._serv_sock = socket.socket()
        self._serv_sock.setblocking(False)
        self._serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._serv_sock.bind((self.RCONConfig["Host"], self.RCONConfig["Port"]))
        self._serv_sock.listen(5)
        self.Peers: List[SourceRCONClient] = []
        self.Password = self.RCONConfig["Password"]

    def Remove(self, Peer: SourceRCONClient) -> None:
        self.Logger.info(
            sys._getframe().f_code.co_name + " Peer {0} disconnected!".format(Peer.Name)
        )
        self.Peers.remove(Peer)

    @asyncio.coroutine
    def _server(self) -> Generator:
        while True:
            PeerSocket: socket.socket
            PeerName: Any
            PeerSocket, PeerName = yield from self.loop.sock_accept(self._serv_sock)
            PeerSocket.setblocking(False)
            Peer = SourceRCONClient(
                self.loop,
                PeerSocket,
                PeerName,
                self.Password,
                self.torchlight_handler.command_handler,
            )
            asyncio.Task(self._peer_handler(Peer))
            self.Peers.append(Peer)
            self.Logger.info(
                sys._getframe().f_code.co_name
                + " Peer {0} connected!".format(Peer.Name)
            )

    @asyncio.coroutine
    def _peer_handler(self, peer: SourceRCONClient) -> Generator:
        try:
            yield from peer._peer_loop()
        except IOError:
            pass
        finally:
            self.Remove(peer)
