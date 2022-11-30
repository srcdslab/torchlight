#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import datetime
import io
import json
import logging
import os
import random
import re
import sys
import tempfile
import traceback
import xml.etree.ElementTree as etree
from re import Match, Pattern
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import geoip2.database
import gtts
import magic
from bs4 import BeautifulSoup
from PIL import Image

from torchlight.AccessManager import AccessManager
from torchlight.AudioManager import AudioManager
from torchlight.Config import Config, ConfigAccess
from torchlight.Player import Player
from torchlight.PlayerManager import PlayerManager
from torchlight.Torchlight import Torchlight
from torchlight.Utils import Utils


class BaseCommand:
    Order = 0

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        self.Logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.audio_manager = audio_manager
        self.player_manager = player_manager
        self.access_manager = access_manager
        self.Triggers: List[Union[str, Pattern]] = []
        self.Level = 0

    def check_chat_cooldown(self, player: Player) -> bool:
        if player.ChatCooldown > self.torchlight.loop.time():
            cooldown = player.ChatCooldown - self.torchlight.loop.time()
            self.torchlight.SayPrivate(
                player,
                "You're on cooldown for the next {0:.1f} seconds.".format(cooldown),
            )
            return True
        return False

    def check_disabled(self, player: Player) -> bool:
        Level: int = 0
        if player.access:
            Level = player.access.level

        disabled = self.torchlight.disabled
        if disabled and (
            disabled > Level
            or disabled == Level
            and Level < self.torchlight.config["AntiSpam"]["ImmunityLevel"]
        ):
            self.torchlight.SayPrivate(player, "Torchlight is currently disabled!")
            return True
        return False

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name)
        return 0

    async def _rfunc(self, line: str, match: Match, player: Player) -> Union[str, int]:
        self.Logger.debug(sys._getframe().f_code.co_name)
        return 0


class URLFilter(BaseCommand):
    Order = 1

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = [
            re.compile(
                r'''(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))''',
                re.IGNORECASE,
            )
        ]
        self.Level: int = -1
        self.re_youtube = re.compile(
            r'.*?(?:youtube\.com\/\S*(?:(?:\/e(?:mbed))?\/|watch\?(?:\S*?&?v\=))|youtu\.be\/)([a-zA-Z0-9_-]{6,11}).*?'
        )

    async def URLInfo(self, url: str, yt: bool = False) -> Tuple[str, Optional[str]]:
        Text = None
        Info = None
        match = self.re_youtube.search(url)
        if match or yt:
            TempPos: int = -1
            Time = None

            if (
                (TempPos := url.find("&t=")) != -1
                or (TempPos := url.find("?t=")) != -1
                or (TempPos := url.find("#t=")) != -1
            ):
                TimeStr = url[TempPos + 3 :].split('&')[0].split('?')[0].split('#')[0]
                if TimeStr:
                    Time = Utils.ParseTime(TimeStr)

            Proc = await asyncio.create_subprocess_exec(
                "youtube-dl", "--dump-json", "-g", url, stdout=asyncio.subprocess.PIPE
            )
            Out, _ = await Proc.communicate()

            parts = Out.split(b'\n')
            parts.pop()  # trailing new line

            Info = parts.pop()
            rawurl = parts.pop()

            url = rawurl.strip().decode("ascii")
            InfoJSON: Dict[str, Any] = json.loads(Info)

            if InfoJSON["extractor_key"] == "Youtube":
                self.torchlight.SayChat(
                    "{{darkred}}[YouTube]{{default}} {0} | {1} | {2:,}".format(
                        InfoJSON["title"],
                        str(datetime.timedelta(seconds=InfoJSON["duration"])),
                        int(InfoJSON["view_count"]),
                    )
                )
            else:
                match = None

            if Time:
                url += "#t={0}".format(Time)

        else:
            try:
                async with aiohttp.ClientSession() as session:
                    Response = await asyncio.wait_for(session.get(url), 5)
                    if Response:
                        ContentType: Optional[str] = Response.headers.get(
                            "Content-Type"
                        )
                        ContentLengthRaw: Optional[str] = Response.headers.get(
                            "Content-Length"
                        )
                        Content = await asyncio.wait_for(
                            Response.content.read(65536), 5
                        )

                        ContentLength = -1
                        if ContentLengthRaw:
                            ContentLength = int(ContentLengthRaw)

                        if ContentType and ContentType.startswith("text"):
                            if ContentType.startswith("text/plain"):
                                Text = Content.decode("utf-8", errors="ignore")
                            else:
                                Soup = BeautifulSoup(
                                    Content.decode("utf-8", errors="ignore"), "lxml"
                                )
                                if Soup.title:
                                    self.torchlight.SayChat(
                                        "[URL] {0}".format(Soup.title.string)
                                    )
                        elif ContentType and ContentType.startswith("image"):
                            fp = io.BytesIO(Content)
                            im = Image.open(fp)
                            self.torchlight.SayChat(
                                "[IMAGE] {0} | Width: {1} | Height: {2} | Size: {3}".format(
                                    im.format,
                                    im.size[0],
                                    im.size[1],
                                    Utils.HumanSize(ContentLength),
                                )
                            )
                            fp.close()
                        else:
                            Filetype = magic.from_buffer(bytes(Content))
                            self.torchlight.SayChat(
                                "[FILE] {0} | Size: {1}".format(
                                    Filetype, Utils.HumanSize(ContentLength)
                                )
                            )

                        Response.close()
            except Exception as e:
                self.torchlight.SayChat("Error: {0}".format(str(e)))
                self.Logger.error(traceback.format_exc())

        self.torchlight.last_url = url
        return url, Text

    async def _rfunc(self, line: str, match: Match, player: Player) -> Union[str, int]:
        Url: str = match.groups()[0]
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


def FormatAccess(config: Config, player: Player) -> str:
    Answer = "#{0} \"{1}\"({2}) is ".format(player.UserID, player.Name, player.UniqueID)
    Level = str(0)
    if player.access:
        Level = str(player.access.level)
        Answer += "level {0!s} as {1}.".format(Level, player.access.name)
    else:
        Answer += "not authenticated."

    if Level in config["AudioLimits"]:
        Uses = config["AudioLimits"][Level]["Uses"]
        TotalTime = config["AudioLimits"][Level]["TotalTime"]

        if Uses >= 0:
            Answer += " Uses: {0}/{1}".format(player.Storage["Audio"]["Uses"], Uses)
        if TotalTime >= 0:
            Answer += " Time: {0}/{1}".format(
                round(player.Storage["Audio"]["TimeUsed"], 2), round(TotalTime, 2)
            )

    return Answer


class Access(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!access"]
        self.Level = self.torchlight.config["CommandLevel"]["Access"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if message[0] == "!access":
            if message[1]:
                return -1

            self.torchlight.SayChat(
                FormatAccess(self.torchlight.config, player), player
            )

        return 0


class Who(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!who", "!whois"]
        self.Level = self.torchlight.config["CommandLevel"]["Who"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        Count = 0
        targeted_player: Optional[Player]
        if message[0] == "!who":
            for targeted_player in self.player_manager:
                if targeted_player.Name.lower().find(message[1].lower()) != -1:
                    self.torchlight.SayChat(
                        FormatAccess(self.torchlight.config, targeted_player)
                    )

                    Count += 1
                    if Count >= 3:
                        break

        elif message[0] == "!whois":
            for UniqueID, access in self.access_manager:
                if access.name.lower().find(message[1].lower()) != -1:
                    targeted_player = self.player_manager.FindUniqueID(UniqueID)
                    if targeted_player is not None:
                        self.torchlight.SayChat(
                            FormatAccess(self.torchlight.config, targeted_player)
                        )
                    else:
                        self.torchlight.SayChat(
                            "#? \"{0}\"({1}) is level {2!s} is currently offline.".format(
                                access.name, UniqueID, access.level
                            )
                        )

                    Count += 1
                    if Count >= 3:
                        break
        return 0


class WolframAlpha(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!cc"]
        self.Level = self.torchlight.config["CommandLevel"]["Calculate"]

    def Clean(self, Text: str) -> str:
        return re.sub(
            "[ ]{2,}",
            " ",
            Text.replace(' | ', ': ').replace('\n', ' | ').replace('~~', ' ≈ '),
        ).strip()

    async def Calculate(self, Params: Dict[str, str], player: Player) -> int:
        async with aiohttp.ClientSession() as session:
            Response = await asyncio.wait_for(
                session.get("http://api.wolframalpha.com/v2/query", params=Params), 10
            )
            if not Response:
                return 1

            Data = await asyncio.wait_for(Response.text(), 5)
            if not Data:
                return 2

        Root = etree.fromstring(Data)

        # Find all pods with plaintext answers
        # Filter out None -answers, strip strings and filter out the empty ones
        Pods: List[str] = list(
            filter(
                None,
                [
                    p.text.strip()
                    for p in Root.findall('.//subpod/plaintext')
                    if p is not None and p.text is not None
                ],
            )
        )

        # no answer pods found, check if there are didyoumeans-elements
        if not Pods:
            Didyoumeans = Root.find("didyoumeans")
            # no support for future stuff yet, TODO?
            if not Didyoumeans:
                # If there's no pods, the question clearly wasn't understood
                self.torchlight.SayChat(
                    "Sorry, couldn't understand the question.", player
                )
                return 3

            Options = []
            for Didyoumean in Didyoumeans:
                Options.append("\"{0}\"".format(Didyoumean.text))
            Line = " or ".join(Options)
            Line = "Did you mean {0}?".format(Line)
            self.torchlight.SayChat(Line, player)
            return 0

        # If there's only one pod with text, it's probably the answer
        # example: "integral x²"
        if len(Pods) == 1:
            Answer = self.Clean(Pods[0])
            self.torchlight.SayChat(Answer, player)
            return 0

        # If there's multiple pods, first is the question interpretation
        Question = self.Clean(Pods[0].replace(' | ', ' ').replace('\n', ' '))
        # and second is the best answer
        Answer = self.Clean(Pods[1])
        self.torchlight.SayChat("{0} = {1}".format(Question, Answer), player)
        return 0

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        Params = dict(
            {"input": message[1], "appid": self.torchlight.config["WolframAPIKey"]}
        )
        Ret = await self.Calculate(Params, player)
        return Ret


class UrbanDictionary(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!define", "!ud"]
        self.Level = self.torchlight.config["CommandLevel"]["Define"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        async with aiohttp.ClientSession() as session:
            Response = await asyncio.wait_for(
                session.get(
                    "https://api.urbandictionary.com/v0/define?term={0}".format(
                        message[1]
                    )
                ),
                5,
            )
            if not Response:
                return 1

            Data = await asyncio.wait_for(Response.json(), 5)
            if not Data:
                return 3

            if not 'list' in Data or not Data["list"]:
                self.torchlight.SayChat(
                    "[UB] No definition found for: {}".format(message[1]), player
                )
                return 4

            def print_item(item: Dict[str, Any]) -> None:
                self.torchlight.SayChat(
                    "[UD] {word} ({thumbs_up}/{thumbs_down}): {definition}\n{example}".format(
                        **item
                    ),
                    player,
                )

            print_item(Data["list"][0])

        return 0


class OpenWeather(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.config_folder = self.torchlight.config["GeoIP"]["Path"]
        self.city_filename = self.torchlight.config["GeoIP"]["CityFilename"]
        self.GeoIP = geoip2.database.Reader(
            f"{self.config_folder}/{self.city_filename}"
        )
        self.Triggers = ["!w", "!vv"]
        self.Level = self.torchlight.config["CommandLevel"]["Weather"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        if not message[1]:
            # Use GeoIP location
            info = self.GeoIP.city(player.Address.split(":")[0])
            Search = "lat={}&lon={}".format(
                info.location.latitude, info.location.longitude
            )
        else:
            Search = "q={}".format(message[1])

        async with aiohttp.ClientSession() as session:
            Response = await asyncio.wait_for(
                session.get(
                    "https://api.openweathermap.org/data/2.5/weather?APPID={0}&units=metric&{1}".format(
                        self.torchlight.config["OpenWeatherAPIKey"], Search
                    )
                ),
                5,
            )
            if not Response:
                return 2

            Data = await asyncio.wait_for(Response.json(), 5)
            if not Data:
                return 3

        if Data["cod"] != 200:
            self.torchlight.SayPrivate(player, "[OW] {0}".format(Data["message"]))
            return 5

        degToCardinal = lambda d: ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][
            int(((d + 22.5) / 45.0) % 8)
        ]
        if "deg" in Data["wind"]:
            windDir = degToCardinal(Data["wind"]["deg"])
        else:
            windDir = "?"

        timezone = "{}{}".format(
            '+' if Data["timezone"] > 0 else '', int(Data["timezone"] / 3600)
        )
        if Data["timezone"] % 3600 != 0:
            timezone += ":{}".format((Data["timezone"] % 3600) / 60)

        self.torchlight.SayChat(
            "[{}, {}](UTC{}) {}°C ({}/{}) {}: {} | Wind {} {}kph | Clouds: {}%% | Humidity: {}%%".format(
                Data["name"],
                Data["sys"]["country"],
                timezone,
                Data["main"]["temp"],
                Data["main"]["temp_min"],
                Data["main"]["temp_max"],
                Data["weather"][0]["main"],
                Data["weather"][0]["description"],
                windDir,
                Data["wind"]["speed"],
                Data["clouds"]["all"],
                Data["main"]["humidity"],
            ),
            player,
        )

        return 0


'''
class WUnderground(BaseCommand):
	def __init__(self, async_client: AsyncClient, access_manager: AccessManager, config: Config) -> None:
		super().__init__(torchlight, access_manager, player_manager, audio_manager)
		self.Triggers = ["!w"]
		self.Level = 0

	async def _func(self, message: List[str], player: Player) -> int:
		if not message[1]:
			# Use IP address
			Search = "autoip"
			Additional = "?geo_ip={0}".format(player.Address.split(":")[0])
		else:
			async with aiohttp.ClientSession() as session:
				Response = await asyncio.wait_for(session.get("http://autocomplete.wunderground.com/aq?format=JSON&query={0}".format(message[1])), 5)
				if not Response:
					return 2

				Data = await asyncio.wait_for(Response.json(), 5)
				if not Data:
					return 3

			if not Data["RESULTS"]:
				self.torchlight.SayPrivate(player, "[WU] No cities match your search query.")
				return 4

			Search = Data["RESULTS"][0]["name"]
			Additional = ""

		async with aiohttp.ClientSession() as session:
			Response = await asyncio.wait_for(session.get("http://api.wunderground.com/api/{0}/conditions/q/{1}.json{2}".format(
				self.torchlight.config["WundergroundAPIKey"], Search, Additional)), 5)
			if not Response:
				return 2

			Data = await asyncio.wait_for(Response.json(), 5)
			if not Data:
				return 3

		if "error" in Data["response"]:
			self.torchlight.SayPrivate(player, "[WU] {0}.".format(Data["response"]["error"]["description"]))
			return 5

		if not "current_observation" in Data:
			Choices = str()
			NumResults = len(Data["response"]["results"])
			for i, Result in enumerate(Data["response"]["results"]):
				Choices += "{0}, {1}".format(Result["city"],
					Result["state"] if Result["state"] else Result ["country_iso3166"])

				if i < NumResults - 1:
					Choices += " | "

			self.torchlight.SayPrivate(player, "[WU] Did you mean: {0}".format(Choices))
			return 6

		Observation = Data["current_observation"]

		self.torchlight.SayChat("[{0}, {1}] {2}°C ({3}F) {4} | Wind {5} {6}kph ({7}mph) | Humidity: {8}".format(Observation["display_location"]["city"],
			Observation["display_location"]["state"] if Observation["display_location"]["state"] else Observation["display_location"]["country_iso3166"],
			Observation["temp_c"], Observation["temp_f"], Observation["weather"],
			Observation["wind_dir"], Observation["wind_kph"], Observation["wind_mph"],
			Observation["relative_humidity"]))

		return 0
'''


class VoteDisable(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!votedisable", "!disablevote"]
        self.Level = self.torchlight.config["CommandLevel"]["VoteDisable"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.torchlight.disabled:
            self.torchlight.SayPrivate(
                player, "Torchlight is already disabled for the duration of this map."
            )
            return -1

        self.torchlight.disable_votes.add(player.UniqueID)

        have = len(self.torchlight.disable_votes)
        needed = len(self.player_manager) // 5
        if have >= needed:
            self.torchlight.SayChat(
                "Torchlight has been disabled for the duration of this map."
            )
            self.torchlight.disabled = 6
        else:
            self.torchlight.SayPrivate(
                player,
                "Torchlight needs {0} more disable votes to be disabled.".format(
                    needed - have
                ),
            )

        return 0


class VoiceCommands(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!random", "!search"]
        self.Level = self.torchlight.config["CommandLevel"]["Search"]

    def LoadTriggers(self) -> None:
        try:
            with open("config/triggers.json", mode="r", encoding='utf-8') as fp:
                Triggers = json.load(fp)
        except ValueError as e:
            self.Logger.error(sys._getframe().f_code.co_name + ' ' + str(e))
            self.torchlight.SayChat(str(e))

        self.VoiceTriggers = dict()
        for Line in Triggers:
            for Trigger in Line["names"]:
                self.VoiceTriggers[Trigger] = Line["sound"]

    def _setup(self) -> None:
        self.Logger.debug(sys._getframe().f_code.co_name)
        self.LoadTriggers()
        for Trigger in self.VoiceTriggers.keys():
            self.Triggers.append(Trigger)

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_disabled(player):
            return -1

        Level = 0
        if player.access:
            Level = player.access.level

        message[0] = message[0].lower()
        message[1] = message[1].lower()

        if (
            message[0] == "!search"
            and Level >= self.torchlight.config["CommandLevel"]["Search"]
        ):
            res = []
            for key in self.VoiceTriggers.keys():
                if message[1] in key.lower():
                    res.append(key)
            self.torchlight.SayPrivate(
                player, "{} results: {}".format(len(res), ", ".join(res))
            )
            return 0

        Sound = None
        if (
            message[0] == "!random"
            and Level >= self.torchlight.config["CommandLevel"]["Random"]
        ):
            Trigger = random.choice(list(self.VoiceTriggers.values()))
            if isinstance(Trigger, list):
                Sound = random.choice(Trigger)
            else:
                Sound = Trigger
        elif Level >= self.torchlight.config["CommandLevel"]["Trigger"]:
            if (
                message[0][0] != '!'
                and Level < self.torchlight.config["CommandLevel"]["TriggerReserved"]
            ):
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
                            self.torchlight.SayPrivate(
                                player,
                                "{} results: {}".format(len(mlist), ", ".join(mlist)),
                            )
                            return 0

                        Sound = matches[0][1]
                        if len(matches) > 1:
                            self.torchlight.SayPrivate(
                                player, "Multiple matches: {}".format(", ".join(mlist))
                            )

                    if not Sound and not Num:
                        if not searching:
                            self.torchlight.SayPrivate(
                                player,
                                "Couldn't find {} in list of sounds.".format(
                                    message[1]
                                ),
                            )
                        self.torchlight.SayPrivate(player, ", ".join(names))
                        return 1

                elif Num:
                    self.torchlight.SayPrivate(
                        player,
                        "Number {} is out of bounds, max {}.".format(Num, len(Sounds)),
                    )
                    return 1

                else:
                    Sound = random.choice(Sounds)
            else:
                Sound = Sounds

        if not Sound:
            return 1

        Path = os.path.abspath(os.path.join("sounds", Sound))
        AudioClip = self.audio_manager.AudioClip(player, "file://" + Path)
        if not AudioClip:
            return 1

        return AudioClip.Play()


class YouTube(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!yt"]
        self.Level = self.torchlight.config["CommandLevel"]["Youtube"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_disabled(player):
            return -1

        if self.torchlight.last_url:
            message[1] = message[1].replace("!last", self.torchlight.last_url)

        TempPos: int = -1
        Time = None

        if (
            (TempPos := message[1].find("&t=")) != -1
            or (TempPos := message[1].find("?t=")) != -1
            or (TempPos := message[1].find("#t=")) != -1
        ):
            TimeStr = (
                message[1][TempPos + 3 :].split('&')[0].split('?')[0].split('#')[0]
            )
            if TimeStr:
                Time = Utils.ParseTime(TimeStr)

        AudioClip = self.audio_manager.AudioClip(player, message[1])
        if not AudioClip:
            return 1

        return AudioClip.Play(Time)


class YouTubeSearch(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!yts"]
        self.Level = self.torchlight.config["CommandLevel"]["YoutubeSearch"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_disabled(player):
            return -1

        TempPos: int = -1
        Time = None

        if (
            (TempPos := message[1].find("&t=")) != -1
            or (TempPos := message[1].find("?t=")) != -1
            or (TempPos := message[1].find("#t=")) != -1
        ):
            TimeStr = (
                message[1][TempPos + 3 :].split('&')[0].split('?')[0].split('#')[0]
            )
            if TimeStr:
                Time = Utils.ParseTime(TimeStr)
            message[1] = message[1][:TempPos]

        Proc = await asyncio.create_subprocess_exec(
            "youtube-dl",
            "--dump-json",
            "-xg",
            "ytsearch:" + message[1],
            stdout=asyncio.subprocess.PIPE,
        )
        Out, _ = await Proc.communicate()

        urlraw, Info = Out.split(b'\n', maxsplit=1)
        url = urlraw.strip().decode("ascii")
        InfoJSON: Dict[str, Any] = json.loads(Info)

        if InfoJSON["extractor_key"] == "Youtube":
            self.torchlight.SayChat(
                "{{darkred}}[YouTube]{{default}} {0} | {1} | {2:,}".format(
                    InfoJSON["title"],
                    str(datetime.timedelta(seconds=InfoJSON["duration"])),
                    int(InfoJSON["view_count"]),
                )
            )

        AudioClip = self.audio_manager.AudioClip(player, url)
        if not AudioClip:
            return 1

        self.torchlight.last_url = url

        return AudioClip.Play(Time)


class Say(BaseCommand):

    try:
        VALID_LANGUAGES = [lang for lang in gtts.lang.tts_langs().keys()]
    except Exception:
        VALID_LANGUAGES = [
            'af',
            'ar',
            'bn',
            'bs',
            'ca',
            'cs',
            'cy',
            'da',
            'de',
            'el',
            'en',
            'eo',
            'es',
            'et',
            'fi',
            'fr',
            'gu',
            'hi',
            'hr',
            'hu',
            'hy',
            'id',
            'is',
            'it',
            'ja',
            'jw',
            'km',
            'kn',
            'ko',
            'la',
            'lv',
            'mk',
            'ml',
            'mr',
            'my',
            'ne',
            'nl',
            'no',
            'pl',
            'pt',
            'ro',
            'ru',
            'si',
            'sk',
            'sq',
            'sr',
            'su',
            'sv',
            'sw',
            'ta',
            'te',
            'th',
            'tl',
            'tr',
            'uk',
            'ur',
            'vi',
            'zh-CN',
            'zh-TW',
            'zh',
        ]

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!say"]
        self.Level = self.torchlight.config["CommandLevel"]["Say"]

    async def Say(self, player: Player, language: str, message: str) -> int:
        GTTS = gtts.gTTS(text=message, lang=language, lang_check=False)

        TempFile = tempfile.NamedTemporaryFile(delete=False)
        GTTS.write_to_fp(TempFile)
        TempFile.close()

        AudioClip = self.audio_manager.AudioClip(player, "file://" + TempFile.name)
        if not AudioClip:
            os.unlink(TempFile.name)
            return 1

        if AudioClip.Play():
            AudioClip.audio_player.AddCallback("Stop", lambda: os.unlink(TempFile.name))
            return 0
        else:
            os.unlink(TempFile.name)
            return 1

    async def _func(self, message: List[str], player: Player) -> int:
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
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!dec"]
        self.Level = self.torchlight.config["CommandLevel"]["Dec"]

    async def Say(self, player: Player, message: str) -> int:
        message = "[:phoneme on]" + message
        TempFile = tempfile.NamedTemporaryFile(delete=False)
        TempFile.close()

        Proc = await asyncio.create_subprocess_exec(
            "./say",
            "-fo",
            TempFile.name,
            cwd="dectalk",
            stdin=asyncio.subprocess.PIPE,
        )
        await Proc.communicate(message.encode('utf-8', errors='ignore'))

        AudioClip = self.audio_manager.AudioClip(player, "file://" + TempFile.name)
        if not AudioClip:
            os.unlink(TempFile.name)
            return 1

        if AudioClip.Play(None, "-af", "volume=10dB"):
            AudioClip.audio_player.AddCallback("Stop", lambda: os.unlink(TempFile.name))
            return 0
        else:
            os.unlink(TempFile.name)
            return 1

        return 0

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if self.check_disabled(player):
            return -1

        if not message[1]:
            return 1

        asyncio.ensure_future(self.Say(player, message[1]))
        return 0


class Stop(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!stop"]
        self.Level = self.torchlight.config["CommandLevel"]["Stop"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        self.audio_manager.Stop(player, message[1])
        return True


class EnableDisable(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!enable", "!disable"]
        self.Level = self.torchlight.config["CommandLevel"]["Enable"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))

        if message[0] == "!enable":
            if self.torchlight.disabled:
                if self.torchlight.disabled > player.access.level:
                    self.torchlight.SayPrivate(
                        player,
                        "You don't have access to enable torchlight, since it was disabled by a higher level user.",
                    )
                    return 1
                self.torchlight.SayChat(
                    "Torchlight has been enabled for the duration of this map - Type !disable to disable it again."
                )

            self.torchlight.disabled = False

        elif message[0] == "!disable":
            if self.torchlight.disabled > player.access.level:
                self.torchlight.SayPrivate(
                    player,
                    "You don't have access to disable torchlight, since it was already disabled by a higher level user.",
                )
                return 1
            self.torchlight.SayChat(
                "Torchlight has been disabled for the duration of this map - Type !enable to enable it again."
            )
            self.torchlight.disabled = player.access.level

        return 0


class AdminAccess(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!access"]
        self.Level: int = self.torchlight.config["CommandLevel"]["AccessAdmin"]

    def ReloadValidUsers(self) -> None:
        self.access_manager.Load()
        for player in self.player_manager:
            access = self.access_manager.get_access(player)
            player.access = access

    async def _func(self, message: List[str], admin_player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))
        if not message[1]:
            return -1

        if message[1].lower() == "reload":
            self.ReloadValidUsers()
            self.torchlight.SayChat(
                "Loaded access list with {0} users".format(len(self.access_manager))
            )

        elif message[1].lower() == "save":
            self.access_manager.Save()
            self.torchlight.SayChat(
                "Saved access list with {0} users".format(len(self.access_manager))
            )

        # Modify access
        else:
            targeted_player: Optional[Player] = None
            Buf = message[1]
            Temp = Buf.find(" as ")
            if Temp != -1:
                try:
                    Regname, LevelParsed = Buf[Temp + 4 :].rsplit(' ', 1)
                except ValueError as e:
                    self.torchlight.SayChat(str(e))
                    return 1

                Regname = Regname.strip()
                LevelParsed = LevelParsed.strip()
                Buf = Buf[:Temp].strip()
            else:
                try:
                    Buf, LevelParsed = Buf.rsplit(' ', 1)
                except ValueError as e:
                    self.torchlight.SayChat(str(e))
                    return 2

                Buf = Buf.strip()
                LevelParsed = LevelParsed.strip()

            # Find user by User ID
            if Buf[0] == '#' and Buf[1:].isnumeric():
                targeted_player = self.player_manager.FindUserID(int(Buf[1:]))
            # Search user by name
            else:
                for player in self.player_manager:
                    if player.Name.lower().find(Buf.lower()) != -1:
                        targeted_player = targeted_player
                        break

            if targeted_player is None:
                self.torchlight.SayChat("Couldn't find user: {0}".format(Buf))
                return 3

            if LevelParsed.isnumeric() or (
                LevelParsed.startswith('-') and LevelParsed[1:].isdigit()
            ):
                Level = int(LevelParsed)

                if (
                    Level >= admin_player.access.level
                    and admin_player.access.level < 10
                ):
                    self.torchlight.SayChat(
                        "Trying to assign level {0}, which is higher or equal than your level ({1})".format(
                            Level, admin_player.access.level
                        )
                    )
                    return 4

                if targeted_player.access:
                    if (
                        targeted_player.access.level >= admin_player.access.level
                        and admin_player.access.level < 10
                    ):
                        self.torchlight.SayChat(
                            "Trying to modify level {0}, which is higher or equal than your level ({1})".format(
                                targeted_player.access.level,
                                admin_player.access.level,
                            )
                        )
                        return 5

                    if "Regname" in locals():
                        self.torchlight.SayChat(
                            "Changed \"{0}\"({1}) as {2} level/name from {3} to {4} as {5}".format(
                                targeted_player.Name,
                                targeted_player.UniqueID,
                                targeted_player.access.name,
                                targeted_player.access.level,
                                Level,
                                Regname,
                            )
                        )
                        targeted_player.access.name = Regname
                    else:
                        self.torchlight.SayChat(
                            "Changed \"{0}\"({1}) as {2} level from {3} to {4}".format(
                                targeted_player.Name,
                                targeted_player.UniqueID,
                                targeted_player.access.name,
                                targeted_player.access.level,
                                Level,
                            )
                        )

                    targeted_player.access.level = Level
                    self.access_manager[
                        targeted_player.UniqueID
                    ] = targeted_player.access
                else:
                    if not "Regname" in locals():
                        Regname = targeted_player.Name

                    access = ConfigAccess(
                        name=Regname, level=Level, uniqueid=targeted_player.UniqueID
                    )
                    self.access_manager[targeted_player.UniqueID] = access
                    targeted_player.access = access
                    self.torchlight.SayChat(
                        "Added \"{0}\"({1}) to access list as {2} with level {3}".format(
                            targeted_player.Name,
                            targeted_player.UniqueID,
                            Regname,
                            Level,
                        )
                    )
            else:
                if Level == "revoke" and targeted_player.access:
                    if (
                        targeted_player.access.level >= admin_player.access.level
                        and admin_player.access.level < 10
                    ):
                        self.torchlight.SayChat(
                            "Trying to revoke level {0}, which is higher or equal than your level ({1})".format(
                                targeted_player.access.level,
                                admin_player.access.level,
                            )
                        )
                        return 6

                    self.torchlight.SayChat(
                        "Removed \"{0}\"({1}) from access list (was {2} with level {3})".format(
                            targeted_player.Name,
                            targeted_player.UniqueID,
                            targeted_player.access.name,
                            targeted_player.access.level,
                        )
                    )
                    access = ConfigAccess(
                        name=targeted_player.Name,
                        level=0,
                        uniqueid=targeted_player.UniqueID,
                    )
                    self.access_manager[targeted_player.UniqueID] = access
                    targeted_player.access = access
        return 0


class Reload(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!reload"]
        self.Level = self.torchlight.config["CommandLevel"]["Reload"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))
        self.torchlight.Reload()
        return 0


class Exec(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.Triggers = ["!exec"]
        self.Level = self.torchlight.config["CommandLevel"]["Exec"]

    async def _func(self, message: List[str], player: Player) -> int:
        self.Logger.debug(sys._getframe().f_code.co_name + ' ' + str(message))
        try:
            Response = eval(message[1])
        except Exception as e:
            self.torchlight.SayChat("Error: {0}".format(str(e)))
            return 1
        self.torchlight.SayChat(str(Response))
        return 0
