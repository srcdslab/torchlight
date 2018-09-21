#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import traceback
import asyncio
import datetime
import time
import socket
import struct
import sys

SAMPLEBYTES = 2

class FFmpegAudioPlayerFactory():
	VALID_CALLBACKS = ["Play", "Stop", "Update"]

	def __init__(self, master):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Master = master
		self.Torchlight = self.Master.Torchlight

	def __del__(self):
		self.Master.Logger.info("~FFmpegAudioPlayerFactory()")
		self.Quit()

	def NewPlayer(self):
		self.Logger.debug(sys._getframe().f_code.co_name)
		Player = FFmpegAudioPlayer(self)
		return Player

	def Quit(self):
		self.Master.Logger.info("FFmpegAudioPlayerFactory->Quit()")


class FFmpegAudioPlayer():
	def __init__(self, master):
		self.Master = master
		self.Torchlight = self.Master.Torchlight
		self.Playing = False

		self.Host = (
			self.Torchlight().Config["VoiceServer"]["Host"],
			self.Torchlight().Config["VoiceServer"]["Port"]
		)
		self.SampleRate = float(self.Torchlight().Config["VoiceServer"]["SampleRate"])

		self.StartedPlaying = None
		self.StoppedPlaying = None
		self.Seconds = 0.0

		self.Writer = None
		self.Process = None

		self.Callbacks = []

	def __del__(self):
		self.Master.Logger.debug("~FFmpegAudioPlayer()")
		self.Stop()

	def PlayURI(self, uri, position, *args):
		if position:
			PosStr = str(datetime.timedelta(seconds = position))
			Command = ["/usr/bin/ffmpeg", "-ss", PosStr, "-i", uri, "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(int(self.SampleRate)), "-f", "s16le", *args, "-"]
		else:
			Command = ["/usr/bin/ffmpeg", "-i", uri, "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(int(self.SampleRate)), "-f", "s16le", *args, "-"]

		print(Command)

		self.Playing = True
		asyncio.ensure_future(self._stream_subprocess(Command))
		return True

	def Stop(self, force = True):
		if not self.Playing:
			return False

		if self.Process:
			try:
				self.Process.terminate()
				self.Process.kill()
				self.Process = None
			except ProcessLookupError:
				pass

		if self.Writer:
			if force:
				Socket = self.Writer.transport.get_extra_info("socket")
				if Socket:
					Socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
						struct.pack("ii", 1, 0))

				self.Writer.transport.abort()

			self.Writer.close()

		self.Playing = False

		self.Callback("Stop")
		del self.Callbacks

		return True

	def AddCallback(self, cbtype, cbfunc):
		if not cbtype in FFmpegAudioPlayerFactory.VALID_CALLBACKS:
			return False

		self.Callbacks.append((cbtype, cbfunc))
		return True

	def Callback(self, cbtype, *args, **kwargs):
		for Callback in self.Callbacks:
			if Callback[0] == cbtype:
				try:
					Callback[1](*args, **kwargs)
				except Exception as e:
					self.Master.Logger.error(traceback.format_exc())

	async def _updater(self):
		LastSecondsElapsed = 0.0

		while self.Playing:
			SecondsElapsed = time.time() - self.StartedPlaying

			if SecondsElapsed > self.Seconds:
				SecondsElapsed = self.Seconds

			self.Callback("Update", LastSecondsElapsed, SecondsElapsed)

			if SecondsElapsed >= self.Seconds:
				if not self.StoppedPlaying:
					print("BUFFER UNDERRUN!")
				self.Stop(False)
				return

			LastSecondsElapsed = SecondsElapsed

			await asyncio.sleep(0.1)

	async def _read_stream(self, stream, writer):
		Started = False

		while stream and self.Playing:
			Data = await stream.read(65536)

			if Data:
				writer.write(Data)
				await writer.drain()

				Bytes = len(Data)
				Samples = Bytes / SAMPLEBYTES
				Seconds = Samples / self.SampleRate

				self.Seconds += Seconds

				if not Started:
					Started = True
					self.Callback("Play")
					self.StartedPlaying = time.time()
					asyncio.ensure_future(self._updater())
			else:
				self.Process = None
				break

		self.StoppedPlaying = time.time()

	async def _stream_subprocess(self, cmd):
		if not self.Playing:
			return

		_, self.Writer = await asyncio.open_connection(self.Host[0], self.Host[1])

		Process = await asyncio.create_subprocess_exec(*cmd,
				stdout = asyncio.subprocess.PIPE, stderr = asyncio.subprocess.DEVNULL)
		self.Process = Process

		await self._read_stream(Process.stdout, self.Writer)
		await Process.wait()

		if self.Seconds == 0.0:
			self.Stop()
