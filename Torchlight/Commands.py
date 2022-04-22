#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import logging
import math
from .Utils import Utils, DataHolder
import traceback

class BaseCommand():
	Order = 0
	def __init__(self, torchlight):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Torchlight = torchlight
		self.Triggers = []
		self.Level = 0

	def check_chat_cooldown(self, player):
		if player.ChatCooldown > self.Torchlight().Master.Loop.time():
			cooldown = player.ChatCooldown - self.Torchlight().Master.Loop.time()
			self.Torchlight().SayPrivate(player, "You're on cooldown for the next {0:.1f} seconds.".format(cooldown))
			return True

	def check_disabled(self, player):
		Level = 0
		if player.Access:
			Level = player.Access["level"]

		Disabled = self.Torchlight().Disabled
		if Disabled and (Disabled > Level or Disabled == Level and Level < self.Torchlight().Config["AntiSpam"]["ImmunityLevel"]):
			self.Torchlight().SayPrivate(player, "Torchlight is currently disabled!")
			return True

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name)


class URLFilter(BaseCommand):
	Order = 1
	import re
	import aiohttp
	import magic
	import datetime
	import json
	import io
	from bs4 import BeautifulSoup
	from PIL import Image
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = [self.re.compile(r'''(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))''', self.re.IGNORECASE)]
		self.Level = -1
		self.re_youtube = self.re.compile(r'.*?(?:youtube\.com\/\S*(?:(?:\/e(?:mbed))?\/|watch\?(?:\S*?&?v\=))|youtu\.be\/)([a-zA-Z0-9_-]{6,11}).*?')

	async def URLInfo(self, url, yt = False):
		Text = None
		Info = None
		match = self.re_youtube.search(url)
		if match or yt:
			Temp = DataHolder()
			Time = None

			if Temp(url.find("&t=")) != -1 or Temp(url.find("?t=")) != -1 or Temp(url.find("#t=")) != -1:
				TimeStr = url[Temp.value + 3:].split('&')[0].split('?')[0].split('#')[0]
				if TimeStr:
					Time = Utils.ParseTime(TimeStr)

			Proc = await asyncio.create_subprocess_exec("youtube-dl", "--dump-json", "-g", url,
				stdout = asyncio.subprocess.PIPE)
			Out, _ = await Proc.communicate()

			parts = Out.split(b'\n')
			parts.pop() # trailing new line

			Info = parts.pop()
			url = parts.pop()

			url = url.strip().decode("ascii")
			Info = self.json.loads(Info)

			if Info["extractor_key"] == "Youtube":
				self.Torchlight().SayChat("\x07E52D27[YouTube]\x01 {0} | {1} | {2:,}".format(
					Info["title"], str(self.datetime.timedelta(seconds = Info["duration"])), int(Info["view_count"])))
			else:
				match = None

			if Time:
				url += "#t={0}".format(Time)

		else:
			try:
				async with self.aiohttp.ClientSession() as session:
					Response = await asyncio.wait_for(session.get(url), 5)
					if Response:
						ContentType = Response.headers.get("Content-Type")
						ContentLength = Response.headers.get("Content-Length")
						Content = await asyncio.wait_for(Response.content.read(65536), 5)

						if not ContentLength:
							ContentLength = -1

						if ContentType.startswith("text"):
							if ContentType.startswith("text/plain"):
								Text = Content.decode("utf-8", errors = "ignore")
							else:
								Soup = self.BeautifulSoup(Content.decode("utf-8", errors = "ignore"), "lxml")
								if Soup.title:
									self.Torchlight().SayChat("[URL] {0}".format(Soup.title.string))
						elif ContentType.startswith("image"):
							fp = self.io.BytesIO(Content)
							im = self.Image.open(fp)
							self.Torchlight().SayChat("[IMAGE] {0} | Width: {1} | Height: {2} | Size: {3}".format(im.format, im.size[0], im.size[1], Utils.HumanSize(ContentLength)))
							fp.close()
						else:
							Filetype = self.magic.from_buffer(bytes(Content))
							self.Torchlight().SayChat("[FILE] {0} | Size: {1}".format(Filetype, Utils.HumanSize(ContentLength)))

						Response.close()
			except Exception as e:
				self.Torchlight().SayChat("Error: {0}".format(str(e)))
				self.Logger.error(traceback.format_exc())

		self.Torchlight().LastUrl = url
		return url, Text

	async def _rfunc(self, line, match, player):
		Url = match.groups()[0]
		if not Url.startswith("http") and not Url.startswith("ftp"):
			Url = "http://" + Url

		if line.startswith("!yt "):
			URL, _ = await self.URLInfo(Url, True)
			return "!yt " + URL

		if line.startswith("!dec "):
			_, text = await self.URLInfo(Url, False)
			if text:
				return "!dec " + text

		asyncio.ensure_future(self.URLInfo(Url))
		return -1


def FormatAccess(Torchlight, player):
	Answer = "#{0} \"{1}\"({2}) is ".format(player.UserID, player.Name, player.UniqueID)
	Level = str(0)
	if player.Access:
		Level = str(player.Access["level"])
		Answer += "level {0!s} as {1}.".format(Level, player.Access["name"])
	else:
		Answer += "not authenticated."

	if Level in Torchlight().Config["AudioLimits"]:
		Uses = Torchlight().Config["AudioLimits"][Level]["Uses"]
		TotalTime = Torchlight().Config["AudioLimits"][Level]["TotalTime"]

		if Uses >= 0:
			Answer += " Uses: {0}/{1}".format(player.Storage["Audio"]["Uses"], Uses)
		if TotalTime >= 0:
			Answer += " Time: {0}/{1}".format(round(player.Storage["Audio"]["TimeUsed"], 2), round(TotalTime, 2))

	return Answer

class Access(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!access"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Access"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_chat_cooldown(player):
			return -1

		Count = 0
		if message[0] == "!access":
			if message[1]:
				return -1

			self.Torchlight().SayChat(FormatAccess(self.Torchlight, player), player)

		return 0

class Who(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!who", "!whois"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Who"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		Count = 0
		if message[0] == "!who":
			for Player in self.Torchlight().Players:
				if Player.Name.lower().find(message[1].lower()) != -1:
					self.Torchlight().SayChat(FormatAccess(self.Torchlight, Player))

					Count += 1
					if Count >= 3:
						break

		elif message[0] == "!whois":
			for UniqueID, Access in self.Torchlight().Access:
				if Access["name"].lower().find(message[1].lower()) != -1:
					Player = self.Torchlight().Players.FindUniqueID(UniqueID)
					if Player:
						self.Torchlight().SayChat(FormatAccess(self.Torchlight, Player))
					else:
						self.Torchlight().SayChat("#? \"{0}\"({1}) is level {2!s} is currently offline.".format(Access["name"], UniqueID, Access["level"]))

					Count += 1
					if Count >= 3:
						break
		return 0


class WolframAlpha(BaseCommand):
	import urllib.parse
	import aiohttp
	import xml.etree.ElementTree as etree
	import re
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!cc"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Calculate"]

	def Clean(self, Text):
		return self.re.sub("[ ]{2,}", " ", Text.replace(' | ', ': ').replace('\n', ' | ').replace('~~', ' ≈ ')).strip()

	async def Calculate(self, Params, player):
		async with self.aiohttp.ClientSession() as session:
			Response = await asyncio.wait_for(session.get("http://api.wolframalpha.com/v2/query", params=Params), 10)
			if not Response:
				return 1

			Data = await asyncio.wait_for(Response.text(), 5)
			if not Data:
				return 2

		Root = self.etree.fromstring(Data)


		# Find all pods with plaintext answers
		# Filter out None -answers, strip strings and filter out the empty ones
		Pods = list(filter(None, [p.text.strip() for p in Root.findall('.//subpod/plaintext') if p is not None and p.text is not None]))

		# no answer pods found, check if there are didyoumeans-elements
		if not Pods:
			Didyoumeans = Root.find("didyoumeans")
			# no support for future stuff yet, TODO?
			if not Didyoumeans:
				# If there's no pods, the question clearly wasn't understood
				self.Torchlight().SayChat("Sorry, couldn't understand the question.", player)
				return 3

			Options = []
			for Didyoumean in Didyoumeans:
				Options.append("\"{0}\"".format(Didyoumean.text))
			Line = " or ".join(Options)
			Line = "Did you mean {0}?".format(Line)
			self.Torchlight().SayChat(Line, player)
			return 0

		# If there's only one pod with text, it's probably the answer
		# example: "integral x²"
		if len(Pods) == 1:
			Answer = self.Clean(Pods[0])
			self.Torchlight().SayChat(Answer, player)
			return 0

		# If there's multiple pods, first is the question interpretation
		Question = self.Clean(Pods[0].replace(' | ', ' ').replace('\n', ' '))
		# and second is the best answer
		Answer = self.Clean(Pods[1])
		self.Torchlight().SayChat("{0} = {1}".format(Question, Answer), player)
		return 0

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_chat_cooldown(player):
			return -1

		if self.check_disabled(player):
			return -1

		Params = dict({"input": message[1], "appid": self.Torchlight().Config["WolframAPIKey"]})
		Ret = await self.Calculate(Params, player)
		return Ret


class UrbanDictionary(BaseCommand):
	import aiohttp
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!define", "!ud"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Define"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_chat_cooldown(player):
			return -1

		if self.check_disabled(player):
			return -1

		async with self.aiohttp.ClientSession() as session:
			Response = await asyncio.wait_for(session.get("https://api.urbandictionary.com/v0/define?term={0}".format(message[1])), 5)
			if not Response:
				return 1

			Data = await asyncio.wait_for(Response.json(), 5)
			if not Data:
				return 3

			if not 'list' in Data or not Data["list"]:
				self.Torchlight().SayChat("[UB] No definition found for: {}".format(message[1]), player)
				return 4

			def print_item(item):
				self.Torchlight().SayChat("[UD] {word} ({thumbs_up}/{thumbs_down}): {definition}\n{example}".format(**item), player)

			print_item(Data["list"][0])


class OpenWeather(BaseCommand):
	import aiohttp
	import geoip2.database
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.GeoIP = self.geoip2.database.Reader("/var/lib/GeoIP/GeoLite2-City.mmdb")
		self.Triggers = ["!w", "!vv"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Weather"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_chat_cooldown(player):
			return -1

		if self.check_disabled(player):
			return -1

		if not message[1]:
			# Use GeoIP location
			info = self.GeoIP.city(player.Address.split(":")[0])
			Search = "lat={}&lon={}".format(info.location.latitude, info.location.longitude)
		else:
			Search = "q={}".format(message[1])

		async with self.aiohttp.ClientSession() as session:
			Response = await asyncio.wait_for(session.get("https://api.openweathermap.org/data/2.5/weather?APPID={0}&units=metric&{1}".format(
				self.Torchlight().Config["OpenWeatherAPIKey"], Search)), 5)
			if not Response:
				return 2

			Data = await asyncio.wait_for(Response.json(), 5)
			if not Data:
				return 3

		if Data["cod"] != 200:
			self.Torchlight().SayPrivate(player, "[OW] {0}".format(Data["message"]))
			return 5

		degToCardinal = lambda d: ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(((d + 22.5)/45.0) % 8)]
		if "deg" in Data["wind"]:
			windDir = degToCardinal(Data["wind"]["deg"])
		else:
			windDir = "?"

		timezone = "{}{}".format('+' if Data["timezone"] > 0 else '', int(Data["timezone"] / 3600))
		if Data["timezone"] % 3600 != 0:
			timezone += ":{}".format((Data["timezone"] % 3600) / 60)

		self.Torchlight().SayChat("[{}, {}](UTC{}) {}°C ({}/{}) {}: {} | Wind {} {}kph | Clouds: {}%% | Humidity: {}%%".format(Data["name"], Data["sys"]["country"], timezone,
			Data["main"]["temp"], Data["main"]["temp_min"], Data["main"]["temp_max"], Data["weather"][0]["main"], Data["weather"][0]["description"],
			windDir, Data["wind"]["speed"], Data["clouds"]["all"], Data["main"]["humidity"]), player)

		return 0

'''
class WUnderground(BaseCommand):
	import aiohttp
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!w"]
		self.Level = 0

	async def _func(self, message, player):
		if not message[1]:
			# Use IP address
			Search = "autoip"
			Additional = "?geo_ip={0}".format(player.Address.split(":")[0])
		else:
			async with self.aiohttp.ClientSession() as session:
				Response = await asyncio.wait_for(session.get("http://autocomplete.wunderground.com/aq?format=JSON&query={0}".format(message[1])), 5)
				if not Response:
					return 2

				Data = await asyncio.wait_for(Response.json(), 5)
				if not Data:
					return 3

			if not Data["RESULTS"]:
				self.Torchlight().SayPrivate(player, "[WU] No cities match your search query.")
				return 4

			Search = Data["RESULTS"][0]["name"]
			Additional = ""

		async with self.aiohttp.ClientSession() as session:
			Response = await asyncio.wait_for(session.get("http://api.wunderground.com/api/{0}/conditions/q/{1}.json{2}".format(
				self.Torchlight().Config["WundergroundAPIKey"], Search, Additional)), 5)
			if not Response:
				return 2

			Data = await asyncio.wait_for(Response.json(), 5)
			if not Data:
				return 3

		if "error" in Data["response"]:
			self.Torchlight().SayPrivate(player, "[WU] {0}.".format(Data["response"]["error"]["description"]))
			return 5

		if not "current_observation" in Data:
			Choices = str()
			NumResults = len(Data["response"]["results"])
			for i, Result in enumerate(Data["response"]["results"]):
				Choices += "{0}, {1}".format(Result["city"],
					Result["state"] if Result["state"] else Result ["country_iso3166"])

				if i < NumResults - 1:
					Choices += " | "

			self.Torchlight().SayPrivate(player, "[WU] Did you mean: {0}".format(Choices))
			return 6

		Observation = Data["current_observation"]

		self.Torchlight().SayChat("[{0}, {1}] {2}°C ({3}F) {4} | Wind {5} {6}kph ({7}mph) | Humidity: {8}".format(Observation["display_location"]["city"],
			Observation["display_location"]["state"] if Observation["display_location"]["state"] else Observation["display_location"]["country_iso3166"],
			Observation["temp_c"], Observation["temp_f"], Observation["weather"],
			Observation["wind_dir"], Observation["wind_kph"], Observation["wind_mph"],
			Observation["relative_humidity"]))

		return 0
'''

class VoteDisable(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!votedisable", "!disablevote"]
		self.Level = self.Torchlight().Config["CommandLevel"]["VoteDisable"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.Torchlight().Disabled:
			self.Torchlight().SayPrivate(player, "Torchlight is already disabled for the duration of this map.")
			return

		self.Torchlight().DisableVotes.add(player.UniqueID)

		have = len(self.Torchlight().DisableVotes)
		needed = len(self.Torchlight().Players) // 5
		if have >= needed:
			self.Torchlight().SayChat("Torchlight has been disabled for the duration of this map.")
			self.Torchlight().Disabled = 6
		else:
			self.Torchlight().SayPrivate(player, "Torchlight needs {0} more disable votes to be disabled.".format(needed - have))


class VoiceCommands(BaseCommand):
	import json
	import random
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!random", "!search"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Search"]

	def LoadTriggers(self):
		try:
			with open("config/triggers.json", mode="r", encoding='utf-8') as fp:
				Triggers = self.json.load(fp)
		except ValueError as e:
			self.Logger.error(sys._getframe().f_code.co_name + ' ' + str(e))
			self.Torchlight().SayChat(str(e))

		self.VoiceTriggers = dict()
		for Line in Triggers:
			for Trigger in Line["names"]:
				self.VoiceTriggers[Trigger] = Line["sound"]

	def _setup(self):
		self.Logger.debug(sys._getframe().f_code.co_name)
		self.LoadTriggers()
		for Trigger in self.VoiceTriggers.keys():
			self.Triggers.append(Trigger)

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_disabled(player):
			return -1

		Level = 0
		if player.Access:
			Level = player.Access["level"]

		message[0] = message[0].lower()
		message[1] = message[1].lower()

		if message[0] == "!search" and Level >= self.Torchlight().Config["CommandLevel"]["Search"]:
			res = []
			for key in self.VoiceTriggers.keys():
				if message[1] in key.lower():
					res.append(key)
			self.Torchlight().SayPrivate(player, "{} results: {}".format(len(res), ", ".join(res)))
			return 0

		Sound = None
		if message[0] == "!random" and Level >= self.Torchlight().Config["CommandLevel"]["Random"]:
			Trigger = self.random.choice(list(self.VoiceTriggers.values()))
			if isinstance(Trigger, list):
				Sound = self.random.choice(Trigger)
			else:
				Sound = Trigger
		elif Level >= self.Torchlight().Config["CommandLevel"]["Trigger"]:
			if message[0][0] != '!' and Level < self.Torchlight().Config["CommandLevel"]["TriggerReserved"]:
				return 1

			Sounds = self.VoiceTriggers[message[0]]

			try:
				Num = int(message[1])
			except ValueError:
				Num = None

			if isinstance(Sounds, list):
				if Num and Num > 0 and Num <= len(Sounds):
					Sound = Sounds[Num - 1]

				elif message[1]:
					searching = message[1].startswith('?')
					search = message[1][1:] if searching else message[1]
					Sound = None
					names = []
					matches = []
					for sound in Sounds:
						name = os.path.splitext(os.path.basename(sound))[0]
						names.append(name)

						if search and search in name.lower():
							matches.append((name, sound))

					if matches:
						matches.sort(key=lambda t: len(t[0]))
						mlist = [t[0] for t in matches]
						if searching:
							self.Torchlight().SayPrivate(player, "{} results: {}".format(len(mlist), ", ".join(mlist)))
							return 0

						Sound = matches[0][1]
						if len(matches) > 1:
							self.Torchlight().SayPrivate(player, "Multiple matches: {}".format(", ".join(mlist)))

					if not Sound and not Num:
						if not searching:
							self.Torchlight().SayPrivate(player, "Couldn't find {} in list of sounds.".format(message[1]))
						self.Torchlight().SayPrivate(player, ", ".join(names))
						return 1

				elif Num:
					self.Torchlight().SayPrivate(player, "Number {} is out of bounds, max {}.".format(Num, len(Sounds)))
					return 1

				else:
					Sound = self.random.choice(Sounds)
			else:
				Sound = Sounds

		if not Sound:
			return 1

		Path = os.path.abspath(os.path.join("sounds", Sound))
		AudioClip = self.Torchlight().AudioManager.AudioClip(player, "file://" + Path)
		if not AudioClip:
			return 1

		return AudioClip.Play()


class YouTube(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!yt"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Youtube"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_disabled(player):
			return -1

		if self.Torchlight().LastUrl:
			message[1] = message[1].replace("!last", self.Torchlight().LastUrl)

		Temp = DataHolder()
		Time = None

		if Temp(message[1].find("&t=")) != -1 or Temp(message[1].find("?t=")) != -1 or Temp(message[1].find("#t=")) != -1:
			TimeStr = message[1][Temp.value + 3:].split('&')[0].split('?')[0].split('#')[0]
			if TimeStr:
				Time = Utils.ParseTime(TimeStr)

		AudioClip = self.Torchlight().AudioManager.AudioClip(player, message[1])
		if not AudioClip:
			return 1

		return AudioClip.Play(Time)

class YouTubeSearch(BaseCommand):
	import json
	import datetime
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!yts"]
		self.Level = self.Torchlight().Config["CommandLevel"]["YoutubeSearch"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_disabled(player):
			return -1

		Temp = DataHolder()
		Time = None

		if Temp(message[1].find("&t=")) != -1 or Temp(message[1].find("?t=")) != -1 or Temp(message[1].find("#t=")) != -1:
			TimeStr = message[1][Temp.value + 3:].split('&')[0].split('?')[0].split('#')[0]
			if TimeStr:
				Time = Utils.ParseTime(TimeStr)
			message[1] = message[1][:Temp.value]

		Proc = await asyncio.create_subprocess_exec("youtube-dl", "--dump-json", "-xg", "ytsearch:" + message[1],
			stdout = asyncio.subprocess.PIPE)
		Out, _ = await Proc.communicate()

		url, Info = Out.split(b'\n', maxsplit = 1)
		url = url.strip().decode("ascii")
		Info = self.json.loads(Info)

		if Info["extractor_key"] == "Youtube":
			self.Torchlight().SayChat("\x07E52D27[YouTube]\x01 {0} | {1} | {2:,}".format(
				Info["title"], str(self.datetime.timedelta(seconds = Info["duration"])), int(Info["view_count"])))

		AudioClip = self.Torchlight().AudioManager.AudioClip(player, url)
		if not AudioClip:
			return 1

		self.Torchlight().LastUrl = url

		return AudioClip.Play(Time)


class Say(BaseCommand):
	import gtts
	import tempfile

	try:
		VALID_LANGUAGES = [lang for lang in gtts.lang.tts_langs().keys()]
	except Exception as err:
		VALID_LANGUAGES = ['af', 'ar', 'bn', 'bs', 'ca', 'cs', 'cy', 'da',
			'de', 'el', 'en', 'eo', 'es', 'et', 'fi', 'fr', 'gu', 'hi',
			'hr', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw', 'km', 'kn',
			'ko', 'la', 'lv', 'mk', 'ml', 'mr', 'my', 'ne', 'nl', 'no',
			'pl', 'pt', 'ro', 'ru', 'si', 'sk', 'sq', 'sr', 'su', 'sv',
			'sw', 'ta', 'te', 'th', 'tl', 'tr', 'uk', 'ur', 'vi', 'zh-CN',
			'zh-TW', 'zh']

	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = [("!say", 4)]
		self.Level = self.Torchlight().Config["CommandLevel"]["Say"]

	async def Say(self, player, language, message):
		GTTS = self.gtts.gTTS(text = message, lang = language, lang_check = False)

		TempFile = self.tempfile.NamedTemporaryFile(delete = False)
		GTTS.write_to_fp(TempFile)
		TempFile.close()

		AudioClip = self.Torchlight().AudioManager.AudioClip(player, "file://" + TempFile.name)
		if not AudioClip:
			os.unlink(TempFile.name)
			return 1

		if AudioClip.Play():
			AudioClip.AudioPlayer.AddCallback("Stop", lambda: os.unlink(TempFile.name))
			return 0
		else:
			os.unlink(TempFile.name)
			return 1

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_disabled(player):
			return -1

		if not message[1]:
			return 1

		Language = "en"
		if len(message[0]) > 4:
			Language = message[0][4:]

		if not Language in self.VALID_LANGUAGES:
			return 1

		asyncio.ensure_future(self.Say(player, Language, message[1]))
		return 0

class DECTalk(BaseCommand):
	import tempfile
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!dec"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Dec"]

	async def Say(self, player, message):
		message = "[:phoneme on]" + message
		TempFile = self.tempfile.NamedTemporaryFile(delete = False)
		TempFile.close()

		Proc = await asyncio.create_subprocess_exec("wine", "say.exe", "-w", TempFile.name,
			cwd = "dectalk", stdin = asyncio.subprocess.PIPE)
		await Proc.communicate(message.encode('utf-8', errors='ignore'))

		AudioClip = self.Torchlight().AudioManager.AudioClip(player, "file://" + TempFile.name)
		if not AudioClip:
			os.unlink(TempFile.name)
			return 1

		if AudioClip.Play(None, "-af", "volume=10dB"):
			AudioClip.AudioPlayer.AddCallback("Stop", lambda: os.unlink(TempFile.name))
			return 0
		else:
			os.unlink(TempFile.name)
			return 1

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if self.check_disabled(player):
			return -1

		if not message[1]:
			return 1

		asyncio.ensure_future(self.Say(player, message[1]))
		return 0

class Stop(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!stop"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Stop"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		self.Torchlight().AudioManager.Stop(player, message[1])
		return True


class EnableDisable(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!enable", "!disable"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Enable"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

		if message[0] == "!enable":
			if self.Torchlight().Disabled:
				if self.Torchlight().Disabled > player.Access["level"]:
					self.Torchlight().SayPrivate(player, "You don't have access to enable torchlight, since it was disabled by a higher level user.")
					return 1
				self.Torchlight().SayChat("Torchlight has been enabled for the duration of this map - Type !disable to disable it again.")

			self.Torchlight().Disabled = False

		elif message[0] == "!disable":
			if self.Torchlight().Disabled > player.Access["level"]:
				self.Torchlight().SayPrivate(player, "You don't have access to disable torchlight, since it was already disabled by a higher level user.")
				return 1
			self.Torchlight().SayChat("Torchlight has been disabled for the duration of this map - Type !enable to enable it again.")
			self.Torchlight().Disabled = player.Access["level"]


class AdminAccess(BaseCommand):
	from collections import OrderedDict
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!access"]
		self.Level = self.Torchlight().Config["CommandLevel"]["AccessAdmin"]

	def ReloadValidUsers(self):
		self.Torchlight().Access.Load()
		for Player in self.Torchlight().Players:
			Access = self.Torchlight().Access[Player.UniqueID]
			Player.Access = Access

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))
		if not message[1]:
			return -1

		if message[1].lower() == "reload":
			self.ReloadValidUsers()
			self.Torchlight().SayChat("Loaded access list with {0} users".format(len(self.Torchlight().Access)))

		elif message[1].lower() == "save":
			self.Torchlight().Access.Save()
			self.Torchlight().SayChat("Saved access list with {0} users".format(len(self.Torchlight().Access)))

		# Modify access
		else:
			Player = None
			Buf = message[1]
			Temp = Buf.find(" as ")
			if Temp != -1:
				try:
					Regname, Level = Buf[Temp + 4:].rsplit(' ', 1)
				except ValueError as e:
					self.Torchlight().SayChat(str(e))
					return 1

				Regname = Regname.strip()
				Level = Level.strip()
				Buf = Buf[:Temp].strip()
			else:
				try:
					Buf, Level = Buf.rsplit(' ', 1)
				except ValueError as e:
					self.Torchlight().SayChat(str(e))
					return 2

				Buf = Buf.strip()
				Level = Level.strip()

			# Find user by User ID
			if Buf[0] == '#' and Buf[1:].isnumeric():
				Player = self.Torchlight().Players.FindUserID(int(Buf[1:]))
			# Search user by name
			else:
				for Player_ in self.Torchlight().Players:
					if Player_.Name.lower().find(Buf.lower()) != -1:
						Player = Player_
						break

			if not Player:
				self.Torchlight().SayChat("Couldn't find user: {0}".format(Buf))
				return 3

			if Level.isnumeric() or (Level.startswith('-') and Level[1:].isdigit()):
				Level = int(Level)

				if Level >= player.Access["level"] and player.Access["level"] < 10:
					self.Torchlight().SayChat("Trying to assign level {0}, which is higher or equal than your level ({1})".format(Level, player.Access["level"]))
					return 4

				if Player.Access:
					if Player.Access["level"] >= player.Access["level"] and player.Access["level"] < 10:
						self.Torchlight().SayChat("Trying to modify level {0}, which is higher or equal than your level ({1})".format(Player.Access["level"], player.Access["level"]))
						return 5

					if "Regname" in locals():
						self.Torchlight().SayChat("Changed \"{0}\"({1}) as {2} level/name from {3} to {4} as {5}".format(
							Player.Name, Player.UniqueID, Player.Access["name"], Player.Access["level"], Level, Regname))
						Player.Access["name"] = Regname
					else:
						self.Torchlight().SayChat("Changed \"{0}\"({1}) as {2} level from {3} to {4}".format(
							Player.Name, Player.UniqueID, Player.Access["name"], Player.Access["level"], Level))

					Player.Access["level"] = Level
					self.Torchlight().Access[Player.UniqueID] = Player.Access
				else:
					if not "Regname" in locals():
						Regname = Player.Name

					self.Torchlight().Access[Player.UniqueID] = self.OrderedDict([("name", Regname), ("level", Level)])
					Player.Access = self.Torchlight().Access[Player.UniqueID]
					self.Torchlight().SayChat("Added \"{0}\"({1}) to access list as {2} with level {3}".format(Player.Name, Player.UniqueID, Regname, Level))
			else:
				if Level == "revoke" and Player.Access:
					if Player.Access["level"] >= player.Access["level"] and player.Access["level"] < 10:
						self.Torchlight().SayChat("Trying to revoke level {0}, which is higher or equal than your level ({1})".format(Player.Access["level"], player.Access["level"]))
						return 6

					self.Torchlight().SayChat("Removed \"{0}\"({1}) from access list (was {2} with level {3})".format(
						Player.Name, Player.UniqueID, Player.Access["name"], Player.Access["level"]))
					del self.Torchlight().Access[Player.UniqueID]
					Player.Access = None
		return 0

class Reload(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!reload"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Reload"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))
		self.Torchlight().Reload()
		return 0


class Exec(BaseCommand):
	def __init__(self, torchlight):
		super().__init__(torchlight)
		self.Triggers = ["!exec"]
		self.Level = self.Torchlight().Config["CommandLevel"]["Exec"]

	async def _func(self, message, player):
		self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))
		try:
			Response = eval(message[1])
		except Exception as e:
			self.Torchlight().SayChat("Error: {0}".format(str(e)))
			return 1
		self.Torchlight().SayChat(str(Response))
		return 0
