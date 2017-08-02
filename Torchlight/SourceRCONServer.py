#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import sys
import socket
import struct
import time
import traceback
from importlib import reload
from .PlayerManager import PlayerManager

class SourceRCONServer():
	class SourceRCONClient():
		def __init__(self, Server, Socket, Name):
			self.Loop = Server.Loop
			self.Server = Server
			self._sock = Socket
			self.Name = Name
			self.Authenticated = False
			asyncio.Task(self._peer_handler())

		def send(self, data):
			return self.Loop.sock_sendall(self._sock, data)

		@asyncio.coroutine
		def _peer_handler(self):
			try:
				yield from self._peer_loop()
			except IOError:
				pass
			finally:
				self.Server.Remove(self)

		@asyncio.coroutine
		def _peer_loop(self):
			while True:
				Data = yield from self.Loop.sock_recv(self._sock, 1024)
				if Data == b'':
					break

				while Data:
					p_size = struct.unpack("<l", Data[:4])[0]
					if len(Data) < p_size+4:
						break
					self.ParsePacket(Data[:p_size+4])
					Data = Data[p_size+4:]

		def p_send(self, p_id, p_type, p_body):
			Data = struct.pack('<l', p_id) + struct.pack('<l', p_type) + p_body.encode("UTF-8") + b'\x00\x00'
			self.send(struct.pack('<l', len(Data)) + Data)

		def ParsePacket(self, Data):
			p_size, p_id, p_type = struct.unpack('<lll', Data[:12])
			Data = Data[12:p_size+2].decode(encoding="UTF-8", errors="ignore").split('\x00')[0]

			if not self.Authenticated:
				if p_type == 3:
					if Data == self.Server.Password:
						self.Authenticated = True
						self.Server.Logger.info(sys._getframe().f_code.co_name + " Connection authenticated from {0}".format(self.Name))
						self.p_send(p_id, 0 , '')
						self.p_send(p_id, 2 , '')
						self.p_send(p_id, 0, "Welcome to torchlight! - Authenticated!\n")
					else:
						self.Server.Logger.info(sys._getframe().f_code.co_name + " Connection denied from {0}".format(self.Name))
						self.p_send(p_id, 0 , '')
						self.p_send(-1, 2 , '')
						self._sock.close()
			else:
				if p_type == 2:
					if Data:
						Data = Data.strip('"')
						self.Server.Logger.info(sys._getframe().f_code.co_name + " Exec: \"{0}\"".format(Data))
						Player = PlayerManager.Player(self.Server.TorchlightHandler.Torchlight.Players, 0, 0, "[CONSOLE]", "127.0.0.1", "CONSOLE")
						Player.Access = dict({"name": "CONSOLE", "level": 9001})
						Player.Storage = dict({"Audio": {"Uses": 0, "LastUse": 0.0, "LastUseLength": 0.0, "TimeUsed": 0.0}})
						asyncio.Task(self.Server.TorchlightHandler.Torchlight.CommandHandler.HandleCommand(Data, Player))
						#self.p_send(p_id, 0, self._server.torchlight.GetLine())

	def __init__(self, Loop, TorchlightHandler, Host="", Port=27015, Password="secret"):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Loop = Loop
		self._serv_sock = socket.socket()
		self._serv_sock.setblocking(0)
		self._serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._serv_sock.bind((Host, Port))
		self._serv_sock.listen(5)
		self.Peers = []
		self.TorchlightHandler = TorchlightHandler
		self.Password = Password
		asyncio.Task(self._server())

	def Remove(self, Peer):
		self.Logger.info(sys._getframe().f_code.co_name + " Peer {0} disconnected!".format(Peer.Name))
		self.Peers.remove(Peer)

	@asyncio.coroutine
	def _server(self):
		while True:
			PeerSocket, PeerName = yield from self.Loop.sock_accept(self._serv_sock)
			PeerSocket.setblocking(0)
			Peer = self.SourceRCONClient(self, PeerSocket, PeerName)
			self.Peers.append(Peer)
			self.Logger.info(sys._getframe().f_code.co_name + " Peer {0} connected!".format(Peer.Name))
