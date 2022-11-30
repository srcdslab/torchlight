#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import socket
import struct
import sys
from typing import Generator, List

from PlayerManager import Player
from Torchlight import TorchlightHandler


class SourceRCONClient:
    def __init__(
        self, Server: SourceRCONServer, Socket: socket.socket, Name: socket._RetAddress
    ):
        self.Loop: asyncio.AbstractEventLoop = Server.Loop
        self.Server: SourceRCONServer = Server
        self._sock: socket.socket = Socket
        self.Name: socket._RetAddress = Name
        self.Authenticated = False
        asyncio.Task(self._peer_handler())

    def send(self, data: bytes):
        return self.Loop.sock_sendall(self._sock, data)

    @asyncio.coroutine
    def _peer_handler(self) -> Generator:
        try:
            yield from self._peer_loop()
        except IOError:
            pass
        finally:
            self.Server.Remove(self)

    @asyncio.coroutine
    def _peer_loop(self) -> Generator:
        while True:
            Data = yield from self.Loop.sock_recv(self._sock, 1024)
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
                if Data == self.Server.Password:
                    self.Authenticated = True
                    self.Server.Logger.info(
                        sys._getframe().f_code.co_name
                        + " Connection authenticated from {0}".format(self.Name)
                    )
                    self.p_send(p_id, 0, '')
                    self.p_send(p_id, 2, '')
                    self.p_send(p_id, 0, "Welcome to torchlight! - Authenticated!\n")
                else:
                    self.Server.Logger.info(
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
                    self.Server.Logger.info(
                        sys._getframe().f_code.co_name + " Exec: \"{0}\"".format(Data)
                    )
                    player = Player(
                        self.Server.TorchlightHandler.Torchlight.Players,
                        0,
                        0,
                        "[CONSOLE]",
                        "127.0.0.1",
                        "CONSOLE",
                    )
                    player.Access = dict({"name": "CONSOLE", "level": 9001})
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
                    asyncio.Task(
                        self.Server.TorchlightHandler.Torchlight.CommandHandler.HandleCommand(
                            Data, player
                        )
                    )
                    # self.p_send(p_id, 0, self._server.torchlight.GetLine())


class SourceRCONServer:
    def __init__(
        self,
        Loop: asyncio.AbstractEventLoop,
        TorchlightHandler: TorchlightHandler,
        Host: str = "",
        Port: int = 27015,
        Password: str = "secret",
    ):
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.Loop: asyncio.AbstractEventLoop = Loop
        self._serv_sock = socket.socket()
        self._serv_sock.setblocking(False)
        self._serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._serv_sock.bind((Host, Port))
        self._serv_sock.listen(5)
        self.Peers: List[SourceRCONClient] = []
        self.TorchlightHandler = TorchlightHandler
        self.Password = Password
        asyncio.Task(self._server())

    def Remove(self, Peer: SourceRCONClient) -> None:
        self.Logger.info(
            sys._getframe().f_code.co_name + " Peer {0} disconnected!".format(Peer.Name)
        )
        self.Peers.remove(Peer)

    @asyncio.coroutine
    def _server(self) -> Generator:
        while True:
            PeerSocket: socket.socket
            PeerName: socket._RetAddress
            PeerSocket, PeerName = yield from self.Loop.sock_accept(self._serv_sock)
            PeerSocket.setblocking(False)
            Peer = SourceRCONClient(self, PeerSocket, PeerName)
            self.Peers.append(Peer)
            self.Logger.info(
                sys._getframe().f_code.co_name
                + " Peer {0} connected!".format(Peer.Name)
            )
