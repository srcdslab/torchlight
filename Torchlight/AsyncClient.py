#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import json

class ClientProtocol(asyncio.Protocol):
	def __init__(self, loop, master):
		self.Loop = loop
		self.Master = master
		self.Transport = None
		self.Buffer = bytearray()

	def connection_made(self, transport):
		self.Transport = transport

	def data_received(self, data):
		self.Buffer += data

		chunks = self.Buffer.split(b'\0')
		if data[-1] == b'\0':
			chunks = chunks[:-1]
			self.Buffer = bytearray()
		else:
			self.Buffer = bytearray(chunks[-1])
			chunks = chunks[:-1]

		for chunk in chunks:
			self.Master.OnReceive(chunk)

	def connection_lost(self, exc):
		self.Transport.close()
		self.Transport = None
		self.Master.OnDisconnect(exc)

	def Send(self, data):
		if self.Transport:
			self.Transport.write(data)

class AsyncClient():
	def __init__(self, loop, host, port, master):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Loop = loop
		self.Host = host
		self.Port = port
		self.Master = master

		self.Protocol = None
		self.SendLock = asyncio.Lock()
		self.RecvFuture = None

	async def Connect(self):
		while True:
			self.Logger.warn("Reconnecting...")
			try:
				_, self.Protocol = await self.Loop.create_connection(
					lambda: ClientProtocol(self.Loop, self), host = self.Host, port = self.Port)
				break
			except:
				await asyncio.sleep(1.0)

	def OnReceive(self, data):
		Obj = json.loads(data)

		if "method" in Obj and Obj["method"] == "publish":
			self.Master.OnPublish(Obj)
		else:
			if self.RecvFuture:
				self.RecvFuture.set_result(Obj)

	def OnDisconnect(self, exc):
		self.Protocol = None
		if self.RecvFuture:
			self.RecvFuture.cancel()
		self.Master.OnDisconnect(exc)

	async def Send(self, obj):
		if not self.Protocol:
			return None

		Data = json.dumps(obj, ensure_ascii = False, separators = (',', ':')).encode("UTF-8")

		async with self.SendLock:
			if not self.Protocol:
				return None

			self.RecvFuture = asyncio.Future()
			self.Protocol.Send(Data)
			await self.RecvFuture

			if self.RecvFuture.done():
				Obj = self.RecvFuture.result()
			else:
				Obj = None

			self.RecvFuture = None
			return Obj
