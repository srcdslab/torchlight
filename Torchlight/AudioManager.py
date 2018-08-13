#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import sys
import io
import math
from .FFmpegAudioPlayer import FFmpegAudioPlayerFactory

class AudioPlayerFactory():
	AUDIOPLAYER_FFMPEG = 1

	def __init__(self, master):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Master = master
		self.Torchlight = self.Master.Torchlight

		self.FFmpegAudioPlayerFactory = FFmpegAudioPlayerFactory(self)

	def __del__(self):
		self.Logger.info("~AudioPlayerFactory()")

	def NewPlayer(self, _type):
		if _type == self.AUDIOPLAYER_FFMPEG:
			return self.FFmpegAudioPlayerFactory.NewPlayer()

class AntiSpam():
	def __init__(self, master):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Master = master
		self.Torchlight = self.Master.Torchlight

		self.LastClips = dict()
		self.DisabledTime = None

	def CheckAntiSpam(self, player):
		if self.DisabledTime and self.DisabledTime > self.Torchlight().Master.Loop.time() and \
			not (player.Access and player.Access["level"] >= self.Torchlight().Config["AntiSpam"]["ImmunityLevel"]):

			self.Torchlight().SayPrivate(player, "Torchlight is currently on cooldown! ({0} seconds left)".format(
				math.ceil(self.DisabledTime - self.Torchlight().Master.Loop.time())))
			return False

		return True

	def RegisterClip(self, clip):
		self.LastClips[hash(clip)] = dict({"timestamp": None, "duration": 0.0, "dominant": False, "active": True})

	def SpamCheck(self):
		Now = self.Torchlight().Master.Loop.time()
		Duration = 0.0

		for Key, Clip in list(self.LastClips.items()):
			if not Clip["timestamp"]:
				continue

			if Clip["timestamp"] + self.Torchlight().Config["AntiSpam"]["MaxUsageSpan"] < Now:
				if not Clip["active"]:
					del self.LastClips[Key]
				continue

			Duration += Clip["duration"]

		if Duration > self.Torchlight().Config["AntiSpam"]["MaxUsageTime"]:
			self.DisabledTime = self.Torchlight().Master.Loop.time() + self.Torchlight().Config["AntiSpam"]["PunishDelay"]
			self.Torchlight().SayChat("Blocked voice commands for the next {0} seconds. Used {1} seconds within {2} seconds.".format(
				self.Torchlight().Config["AntiSpam"]["PunishDelay"], self.Torchlight().Config["AntiSpam"]["MaxUsageTime"], self.Torchlight().Config["AntiSpam"]["MaxUsageSpan"]))

			# Make a copy of the list since AudioClip.Stop() will change the list
			for AudioClip in self.Master.AudioClips[:]:
				if AudioClip.Level < self.Torchlight().Config["AntiSpam"]["ImmunityLevel"]:
					AudioClip.Stop()

			self.LastClips.clear()

	def OnPlay(self, clip):
		self.LastClips[hash(clip)]["timestamp"] = self.Torchlight().Master.Loop.time()

		HasDominant = False
		for Key, Clip in self.LastClips.items():
			if Clip["dominant"]:
				HasDominant = True
				break

		self.LastClips[hash(clip)]["dominant"] = not HasDominant

	def OnStop(self, clip):
		self.LastClips[hash(clip)]["active"] = False

		if self.LastClips[hash(clip)]["dominant"]:
			for Key, Clip in self.LastClips.items():
				if Clip["active"]:
					Clip["dominant"] = True
					break

		self.LastClips[hash(clip)]["dominant"] = False

	def OnUpdate(self, clip, old_position, new_position):
		Delta = new_position - old_position
		Clip = self.LastClips[hash(clip)]

		if not Clip["dominant"]:
			return

		Clip["duration"] += Delta
		self.SpamCheck()


class AudioManager():
	def __init__(self, torchlight):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Torchlight = torchlight
		self.AntiSpam = AntiSpam(self)
		self.AudioPlayerFactory = AudioPlayerFactory(self)
		self.AudioClips = []

	def __del__(self):
		self.Logger.info("~AudioManager()")

	def CheckLimits(self, player):
		Level = 0
		if player.Access:
			Level = player.Access["level"]

		if str(Level) in self.Torchlight().Config["AudioLimits"]:
			if self.Torchlight().Config["AudioLimits"][str(Level)]["Uses"] >= 0 and \
				player.Storage["Audio"]["Uses"] >= self.Torchlight().Config["AudioLimits"][str(Level)]["Uses"]:

				self.Torchlight().SayPrivate(player, "You have used up all of your free uses! ({0} uses)".format(
					self.Torchlight().Config["AudioLimits"][str(Level)]["Uses"]))
				return False

			if player.Storage["Audio"]["TimeUsed"] >= self.Torchlight().Config["AudioLimits"][str(Level)]["TotalTime"]:
				self.Torchlight().SayPrivate(player, "You have used up all of your free time! ({0} seconds)".format(
					self.Torchlight().Config["AudioLimits"][str(Level)]["TotalTime"]))
				return False

			TimeElapsed = self.Torchlight().Master.Loop.time() - player.Storage["Audio"]["LastUse"]
			UseDelay = player.Storage["Audio"]["LastUseLength"] * self.Torchlight().Config["AudioLimits"][str(Level)]["DelayFactor"]

			if TimeElapsed < UseDelay:
				self.Torchlight().SayPrivate(player, "You are currently on cooldown! ({0} seconds left)".format(
					round(UseDelay - TimeElapsed)))
				return False

		return True

	def Stop(self, player, extra):
		Level = 0
		if player.Access:
			Level = player.Access["level"]

		for AudioClip in self.AudioClips[:]:
			if extra and not extra.lower() in AudioClip.Player.Name.lower():
					continue

			if not Level or Level < AudioClip.Level:
				AudioClip.Stops.add(player.UserID)

				if len(AudioClip.Stops) >= 3:
					AudioClip.Stop()
					self.Torchlight().SayPrivate(AudioClip.Player, "Your audio clip was stopped.")
					if player != AudioClip.Player:
						self.Torchlight().SayPrivate(player, "Stopped \"{0}\"({1}) audio clip.".format(AudioClip.Player.Name, AudioClip.Player.UserID))
				else:
					self.Torchlight().SayPrivate(player, "This audio clip needs {0} more !stop's.".format(3 - len(AudioClip.Stops)))
			else:
				AudioClip.Stop()
				self.Torchlight().SayPrivate(AudioClip.Player, "Your audio clip was stopped.")
				if player != AudioClip.Player:
					self.Torchlight().SayPrivate(player, "Stopped \"{0}\"({1}) audio clip.".format(AudioClip.Player.Name, AudioClip.Player.UserID))

	def AudioClip(self, player, uri, _type = AudioPlayerFactory.AUDIOPLAYER_FFMPEG):
		Level = 0
		if player.Access:
			Level = player.Access["level"]

		if self.Torchlight().Disabled and self.Torchlight().Disabled > Level:
			self.Torchlight().SayPrivate(player, "Torchlight is currently disabled!")
			return None

		if not self.AntiSpam.CheckAntiSpam(player):
			return None

		if not self.CheckLimits(player):
			return None

		Clip = AudioClip(self, player, uri, _type)
		self.AudioClips.append(Clip)

		if not player.Access or player.Access["level"] < self.Torchlight().Config["AntiSpam"]["ImmunityLevel"]:
			self.AntiSpam.RegisterClip(Clip)
			Clip.AudioPlayer.AddCallback("Play", lambda *args: self.AntiSpam.OnPlay(Clip, *args))
			Clip.AudioPlayer.AddCallback("Stop", lambda *args: self.AntiSpam.OnStop(Clip, *args))
			Clip.AudioPlayer.AddCallback("Update", lambda *args: self.AntiSpam.OnUpdate(Clip, *args))

		return Clip

	def OnDisconnect(self, player):
		for AudioClip in self.AudioClips[:]:
			if AudioClip.Player == player:
				AudioClip.Stop()


class AudioClip():
	def __init__(self, master, player, uri, _type):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Master = master
		self.Torchlight = self.Master.Torchlight
		self.Player = player
		self.Type = _type
		self.URI = uri
		self.LastPosition = None
		self.Stops = set()

		self.Level = 0
		if self.Player.Access:
			self.Level = self.Player.Access["level"]

		self.AudioPlayer = self.Master.AudioPlayerFactory.NewPlayer(self.Type)
		self.AudioPlayer.AddCallback("Play", self.OnPlay)
		self.AudioPlayer.AddCallback("Stop", self.OnStop)
		self.AudioPlayer.AddCallback("Update", self.OnUpdate)

	def __del__(self):
		self.Logger.info("~AudioClip()")

	def Play(self, seconds = None):
		return self.AudioPlayer.PlayURI(self.URI, seconds)

	def Stop(self):
		return self.AudioPlayer.Stop()

	def OnPlay(self):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + self.URI)

		self.Player.Storage["Audio"]["Uses"] += 1
		self.Player.Storage["Audio"]["LastUse"] = self.Torchlight().Master.Loop.time()
		self.Player.Storage["Audio"]["LastUseLength"] = 0.0

	def OnStop(self):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + self.URI)
		self.Master.AudioClips.remove(self)

		if self.AudioPlayer.Playing:
			Delta = self.AudioPlayer.Position - self.LastPosition
			self.Player.Storage["Audio"]["TimeUsed"] += Delta
			self.Player.Storage["Audio"]["LastUseLength"] += Delta

		if str(self.Level) in self.Torchlight().Config["AudioLimits"]:
			if self.Player:
				if self.Player.Storage["Audio"]["TimeUsed"] >= self.Torchlight().Config["AudioLimits"][str(self.Level)]["TotalTime"]:
					self.Torchlight().SayPrivate(self.Player, "You have used up all of your free time! ({0} seconds)".format(
						self.Torchlight().Config["AudioLimits"][str(self.Level)]["TotalTime"]))
				elif self.Player.Storage["Audio"]["LastUseLength"] >= self.Torchlight().Config["AudioLimits"][str(self.Level)]["MaxLength"]:
					self.Torchlight().SayPrivate(self.Player, "Your audio clip exceeded the maximum length! ({0} seconds)".format(
						self.Torchlight().Config["AudioLimits"][str(self.Level)]["MaxLength"]))

		del self.AudioPlayer

	def OnUpdate(self, old_position, new_position):
		Delta = new_position - old_position
		self.LastPosition = new_position

		self.Player.Storage["Audio"]["TimeUsed"] += Delta
		self.Player.Storage["Audio"]["LastUseLength"] += Delta

		if not str(self.Level) in self.Torchlight().Config["AudioLimits"]:
			return

		if (self.Player.Storage["Audio"]["TimeUsed"] >= self.Torchlight().Config["AudioLimits"][str(self.Level)]["TotalTime"] or
			self.Player.Storage["Audio"]["LastUseLength"] >= self.Torchlight().Config["AudioLimits"][str(self.Level)]["MaxLength"]):
			self.Stop()
