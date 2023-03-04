#!/usr/bin/python3
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
from typing import Any

import aiohttp
import geoip2.database
import gtts
import magic
from bs4 import BeautifulSoup
from PIL import Image

from torchlight.AccessManager import AccessManager
from torchlight.AudioManager import AudioManager
from torchlight.Config import Config
from torchlight.Player import Player
from torchlight.PlayerManager import PlayerManager
from torchlight.Torchlight import Torchlight
from torchlight.Utils import Utils


class BaseCommand:
    order = 0

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.audio_manager = audio_manager
        self.player_manager = player_manager
        self.access_manager = access_manager
        self.triggers: list[tuple[str, int] | str | Pattern] = []
        self.level = 0

    def check_chat_cooldown(self, player: Player) -> bool:
        if player.chat_cooldown > self.torchlight.loop.time():
            cooldown = player.chat_cooldown - self.torchlight.loop.time()
            self.torchlight.SayPrivate(
                player,
                f"You're on cooldown for the next {cooldown:.1f} seconds.",
            )
            return True
        return False

    def check_disabled(self, player: Player) -> bool:
        level = player.access.level

        disabled = self.torchlight.disabled
        if disabled and (
            disabled > level
            or disabled == level
            and level < self.torchlight.config["AntiSpam"]["ImmunityLevel"]
        ):
            self.torchlight.SayPrivate(player, "Torchlight is currently disabled!")
            return True
        return False

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name)
        return 0

    async def _rfunc(self, line: str, match: Match, player: Player) -> str | int:
        self.logger.debug(sys._getframe().f_code.co_name)
        return 0


class URLFilter(BaseCommand):
    order = 1

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = [
            re.compile(
                r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""",
                re.IGNORECASE,
            )
        ]
        self.level: int = -1
        self.re_youtube = re.compile(
            r".*?(?:youtube\.com\/\S*(?:(?:\/e(?:mbed))?\/|watch\?(?:\S*?&?v\=))|youtu\.be\/)([a-zA-Z0-9_-]{6,11}).*?"
        )

    async def URLInfo(self, url: str, yt: bool = False) -> tuple[str, str | None]:
        text = None
        info = None
        match = self.re_youtube.search(url)
        if match or yt:
            temp_pos: int = -1
            real_time = None

            if (
                (temp_pos := url.find("&t=")) != -1
                or (temp_pos := url.find("?t=")) != -1
                or (temp_pos := url.find("#t=")) != -1
            ):
                time_str = url[temp_pos + 3 :].split("&")[0].split("?")[0].split("#")[0]
                if time_str:
                    real_time = Utils.ParseTime(time_str)

            subprocess = await asyncio.create_subprocess_exec(
                "youtube-dl", "--dump-json", "-g", url, stdout=asyncio.subprocess.PIPE
            )
            output, _ = await subprocess.communicate()

            parts = output.split(b"\n")
            parts.pop()  # trailing new line

            info = parts.pop()
            raw_url = parts.pop()

            url = raw_url.strip().decode("ascii")
            json_info: dict[str, Any] = json.loads(info)

            if json_info["extractor_key"] == "Youtube":
                self.torchlight.SayChat(
                    "{{darkred}}[YouTube]{{default}} {0} | {1} | {2:,}".format(
                        json_info["title"],
                        str(datetime.timedelta(seconds=json_info["duration"])),
                        int(json_info["view_count"]),
                    )
                )
            else:
                match = None

            if real_time:
                url += f"#t={real_time}"

        else:
            try:
                async with aiohttp.ClientSession() as session:
                    resp = await asyncio.wait_for(session.get(url), 5)
                    if resp:
                        content_type: str | None = resp.headers.get("Content-Type")
                        content_length_raw: str | None = resp.headers.get(
                            "Content-Length"
                        )
                        content = await asyncio.wait_for(resp.content.read(65536), 5)

                        content_length = -1
                        if content_length_raw:
                            content_length = int(content_length_raw)

                        if content_type and content_type.startswith("text"):
                            if content_type.startswith("text/plain"):
                                text = content.decode("utf-8", errors="ignore")
                            else:
                                Soup = BeautifulSoup(
                                    content.decode("utf-8", errors="ignore"), "lxml"
                                )
                                if Soup.title:
                                    self.torchlight.SayChat(
                                        f"[URL] {Soup.title.string}"
                                    )
                        elif content_type and content_type.startswith("image"):
                            fp = io.BytesIO(content)
                            im = Image.open(fp)
                            self.torchlight.SayChat(
                                "[IMAGE] {} | Width: {} | Height: {} | Size: {}".format(
                                    im.format,
                                    im.size[0],
                                    im.size[1],
                                    Utils.HumanSize(content_length),
                                )
                            )
                            fp.close()
                        else:
                            Filetype = magic.from_buffer(bytes(content))
                            self.torchlight.SayChat(
                                "[FILE] {} | Size: {}".format(
                                    Filetype, Utils.HumanSize(content_length)
                                )
                            )

                        resp.close()
            except Exception as e:
                self.torchlight.SayChat(f"Error: {str(e)}")
                self.logger.error(traceback.format_exc())

        self.torchlight.last_url = url
        return url, text

    async def _rfunc(self, line: str, match: Match, player: Player) -> str | int:
        url: str = match.groups()[0]
        if not url.startswith("http") and not url.startswith("ftp"):
            url = "http://" + url

        if line.startswith("!yt "):
            url, _ = await self.URLInfo(url, True)
            return "!yt " + url

        if line.startswith("!dec "):
            _, text = await self.URLInfo(url, False)
            if text:
                return "!dec " + text

        asyncio.ensure_future(self.URLInfo(url))
        return -1


def FormatAccess(config: Config, player: Player) -> str:
    answer = f'#{player.user_id} "{player.name}"({player.unique_id}) is '
    level = str(player.access.level)
    answer += f"level {level!s} as {player.access.name}."

    if level in config["AudioLimits"]:
        uses = config["AudioLimits"][level]["Uses"]
        total_time = config["AudioLimits"][level]["TotalTime"]

        if uses >= 0:
            answer += " Uses: {}/{}".format(player.storage["Audio"]["Uses"], uses)
        if total_time >= 0:
            answer += " Time: {}/{}".format(
                round(player.storage["Audio"]["TimeUsed"], 2), round(total_time, 2)
            )

    return answer


class Access(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = ["!access"]
        self.level = self.torchlight.config["CommandLevel"]["Access"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

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
        self.triggers = ["!who", "!whois"]
        self.level = self.torchlight.config["CommandLevel"]["Who"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        Count = 0
        if message[0] == "!who":
            for targeted_player in self.player_manager.players:
                if (
                    targeted_player
                    and targeted_player.name.lower().find(message[1].lower()) != -1
                ):
                    self.torchlight.SayChat(
                        FormatAccess(self.torchlight.config, targeted_player)
                    )

                    Count += 1
                    if Count >= 3:
                        break

        elif message[0] == "!whois":
            for unique_id, access in self.access_manager.config_access_list.items():
                if access.name.lower().find(message[1].lower()) != -1:
                    targeted_player = self.player_manager.FindUniqueID(unique_id)
                    if targeted_player is not None:
                        self.torchlight.SayChat(
                            FormatAccess(self.torchlight.config, targeted_player)
                        )
                    else:
                        self.torchlight.SayChat(
                            '#? "{}"({}) is level {!s} is currently offline.'.format(
                                access.name, unique_id, access.level
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
        self.triggers = ["!cc"]
        self.level = self.torchlight.config["CommandLevel"]["Calculate"]

    def Clean(self, text: str) -> str:
        return re.sub(
            "[ ]{2,}",
            " ",
            text.replace(" | ", ": ").replace("\n", " | ").replace("~~", " ≈ "),
        ).strip()

    async def Calculate(self, parameters_json: dict[str, str], player: Player) -> int:
        async with aiohttp.ClientSession() as session:
            resp = await asyncio.wait_for(
                session.get(
                    "http://api.wolframalpha.com/v2/query", params=parameters_json
                ),
                10,
            )
            if not resp:
                return 1

            data = await asyncio.wait_for(resp.text(), 5)
            if not data:
                return 2

        root = etree.fromstring(data)

        # Find all pods with plaintext answers
        # Filter out None -answers, strip strings and filter out the empty ones
        pods: list[str] = list(
            filter(
                None,
                [
                    p.text.strip()
                    for p in root.findall(".//subpod/plaintext")
                    if p is not None and p.text is not None
                ],
            )
        )

        # no answer pods found, check if there are didyoumeans-elements
        if not pods:
            did_you_means = root.find("didyoumeans")
            # no support for future stuff yet, TODO?
            if not did_you_means:
                # If there's no pods, the question clearly wasn't understood
                self.torchlight.SayChat(
                    "Sorry, couldn't understand the question.", player
                )
                return 3

            options = []
            for did_you_mean in did_you_means:
                options.append(f'"{did_you_mean.text}"')
            line = " or ".join(options)
            line = f"Did you mean {line}?"
            self.torchlight.SayChat(line, player)
            return 0

        # If there's only one pod with text, it's probably the answer
        # example: "integral x²"
        if len(pods) == 1:
            answer = self.Clean(pods[0])
            self.torchlight.SayChat(answer, player)
            return 0

        # If there's multiple pods, first is the question interpretation
        question = self.Clean(pods[0].replace(" | ", " ").replace("\n", " "))
        # and second is the best answer
        answer = self.Clean(pods[1])
        self.torchlight.SayChat(f"{question} = {answer}", player)
        return 0

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if not self.torchlight.config["WolframAPIKey"]:
            self.torchlight.SayPrivate(
                message="WolframAlpha is not configured (API key missing)",
                player=player,
            )
            return 1

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        parameters_json = dict(
            {"input": message[1], "appid": self.torchlight.config["WolframAPIKey"]}
        )
        ret = await self.Calculate(parameters_json, player)
        return ret


class UrbanDictionary(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = ["!define", "!ud"]
        self.level = self.torchlight.config["CommandLevel"]["Define"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        async with aiohttp.ClientSession() as session:
            resp = await asyncio.wait_for(
                session.get(
                    "https://api.urbandictionary.com/v0/define?term={}".format(
                        message[1]
                    )
                ),
                5,
            )
            if not resp:
                return 1

            data = await asyncio.wait_for(resp.json(), 5)
            if not data:
                return 3

            if "list" not in data or not data["list"]:
                self.torchlight.SayChat(
                    f"[UB] No definition found for: {message[1]}", player
                )
                return 4

            def print_item(item: dict[str, Any]) -> None:
                self.torchlight.SayChat(
                    "[UD] {word} ({thumbs_up}/{thumbs_down}): {definition}\n{example}".format(
                        **item
                    ),
                    player,
                )

            print_item(data["list"][0])

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
        self.geo_ip = geoip2.database.Reader(
            f"{self.config_folder}/{self.city_filename}"
        )
        self.triggers = ["!w", "!vv"]
        self.level = self.torchlight.config["CommandLevel"]["Weather"]

    def degreeToCardinal(self, degree: int) -> str:
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return directions[int(((degree + 22.5) / 45.0) % 8)]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        if not message[1]:
            # Use GeoIP location
            info = self.geo_ip.city(player.address.split(":")[0])
            search = "lat={}&lon={}".format(
                info.location.latitude, info.location.longitude
            )
        else:
            search = f"q={message[1]}"

        async with aiohttp.ClientSession() as session:
            resp = await asyncio.wait_for(
                session.get(
                    "https://api.openweathermap.org/data/2.5/weather?APPID={}&units=metric&{}".format(
                        self.torchlight.config["OpenWeatherAPIKey"], search
                    )
                ),
                5,
            )
            if not resp:
                return 2

            data = await asyncio.wait_for(resp.json(), 5)
            if not data:
                return 3

        if data["cod"] != 200:
            self.torchlight.SayPrivate(player, "[OW] {}".format(data["message"]))
            return 5

        if "deg" in data["wind"]:
            windDir = self.degreeToCardinal(data["wind"]["deg"])
        else:
            windDir = "?"

        timezone = "{}{}".format(
            "+" if data["timezone"] > 0 else "", int(data["timezone"] / 3600)
        )
        if data["timezone"] % 3600 != 0:
            timezone += ":{}".format((data["timezone"] % 3600) / 60)

        self.torchlight.SayChat(
            "[{}, {}](UTC{}) {}°C ({}/{}) {}: {} | Wind {} {}kph | Clouds: {}%% | Humidity: {}%%".format(
                data["name"],
                data["sys"]["country"],
                timezone,
                data["main"]["temp"],
                data["main"]["temp_min"],
                data["main"]["temp_max"],
                data["weather"][0]["main"],
                data["weather"][0]["description"],
                windDir,
                data["wind"]["speed"],
                data["clouds"]["all"],
                data["main"]["humidity"],
            ),
            player,
        )

        return 0


class WUnderground(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = ["!wunder"]
        self.level = self.torchlight.config["CommandLevel"]["Weather"]

    async def _func(self, message: list[str], player: Player) -> int:
        if not self.torchlight.config["WundergroundAPIKey"]:
            self.torchlight.SayPrivate(
                message="Wunderground is not configured (API key missing)",
                player=player,
            )
            return 1

        if not message[1]:
            # Use IP address
            search = "autoip"
            additional = "?geo_ip={}".format(player.address.split(":")[0])
        else:
            async with aiohttp.ClientSession() as session:
                resp = await asyncio.wait_for(
                    session.get(
                        "http://autocomplete.wunderground.com/aq?format=JSON&query={}".format(
                            message[1]
                        )
                    ),
                    5,
                )
                if not resp:
                    return 2

                try:
                    data = await asyncio.wait_for(resp.json(), 5)
                    if not data:
                        return 3
                except Exception as e:
                    self.logger.error(e)
                    self.torchlight.SayPrivate(
                        message="Failed to retrieve data from the wunderground api",
                        player=player,
                    )
                    return 1

            if not data["RESULTS"]:
                self.torchlight.SayPrivate(
                    player, "[WU] No cities match your search query."
                )
                return 4

            search = data["RESULTS"][0]["name"]
            additional = ""

        async with aiohttp.ClientSession() as session:
            resp = await asyncio.wait_for(
                session.get(
                    "http://api.wunderground.com/api/{}/conditions/q/{}.json{}".format(
                        self.torchlight.config["WundergroundAPIKey"], search, additional
                    )
                ),
                5,
            )
            if not resp:
                return 2

            try:
                data = await asyncio.wait_for(resp.json(), 5)
                if not data:
                    return 3
            except Exception as e:
                self.logger.error(e)
                self.torchlight.SayPrivate(
                    message="Failed to retrieve data from the wunderground api",
                    player=player,
                )
                return 1

        if "error" in data["response"]:
            self.torchlight.SayPrivate(
                player, "[WU] {}.".format(data["response"]["error"]["description"])
            )
            return 5

        if "current_observation" not in data:
            choices = ""
            num_results = len(data["response"]["results"])
            for i, result in enumerate(data["response"]["results"]):
                choices += "{}, {}".format(
                    result["city"],
                    result["state"] if result["state"] else result["country_iso3166"],
                )

                if i < num_results - 1:
                    choices += " | "

            self.torchlight.SayPrivate(player, f"[WU] Did you mean: {choices}")
            return 6

        curr_observation = data["current_observation"]

        self.torchlight.SayChat(
            "[{}, {}] {}°C ({}F) {} | Wind {} {}kph ({}mph) | Humidity: {}".format(
                curr_observation["display_location"]["city"],
                curr_observation["display_location"]["state"]
                if curr_observation["display_location"]["state"]
                else curr_observation["display_location"]["country_iso3166"],
                curr_observation["temp_c"],
                curr_observation["temp_f"],
                curr_observation["weather"],
                curr_observation["wind_dir"],
                curr_observation["wind_kph"],
                curr_observation["wind_mph"],
                curr_observation["relative_humidity"],
            )
        )

        return 0


class VoteDisable(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = ["!votedisable", "!disablevote"]
        self.level = self.torchlight.config["CommandLevel"]["VoteDisable"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.torchlight.disabled:
            self.torchlight.SayPrivate(
                player, "Torchlight is already disabled for the duration of this map."
            )
            return -1

        self.torchlight.disable_votes.add(player.unique_id)

        have = len(self.torchlight.disable_votes)
        needed = self.player_manager.player_count // 5
        if have >= needed:
            self.torchlight.SayChat(
                "Torchlight has been disabled for the duration of this map."
            )
            self.torchlight.disabled = 6
        else:
            self.torchlight.SayPrivate(
                player,
                "Torchlight needs {} more disable votes to be disabled.".format(
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
        self.triggers = ["!random", "!search"]
        self.level = self.torchlight.config["CommandLevel"]["Search"]

    def LoadTriggers(self) -> None:
        try:
            with open("config/triggers.json", encoding="utf-8") as fp:
                triggers = json.load(fp)
        except ValueError as e:
            self.logger.error(sys._getframe().f_code.co_name + " " + str(e))
            self.torchlight.SayChat(str(e))

        self.voice_triggers = {}
        for line in triggers:
            for trigger in line["names"]:
                self.voice_triggers[trigger] = line["sound"]

    def _setup(self) -> None:
        self.logger.debug(sys._getframe().f_code.co_name)
        self.LoadTriggers()
        for trigger in self.voice_triggers.keys():
            self.triggers.append(trigger)

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        level = player.access.level

        message[0] = message[0].lower()
        message[1] = message[1].lower()

        if (
            message[0] == "!search"
            and level >= self.torchlight.config["CommandLevel"]["Search"]
        ):
            res = []
            for key in self.voice_triggers.keys():
                if message[1] in key.lower():
                    res.append(key)
            self.torchlight.SayPrivate(
                player, "{} results: {}".format(len(res), ", ".join(res))
            )
            return 0

        sound = None
        if (
            message[0] == "!random"
            and level >= self.torchlight.config["CommandLevel"]["Random"]
        ):
            trigger = random.choice(list(self.voice_triggers.values()))
            if isinstance(trigger, list):
                sound = random.choice(trigger)
            else:
                sound = trigger
        elif level >= self.torchlight.config["CommandLevel"]["Trigger"]:
            if (
                message[0][0] != "!"
                and level < self.torchlight.config["CommandLevel"]["TriggerReserved"]
            ):
                return 1

            sounds = self.voice_triggers[message[0]]

            try:
                num = int(message[1])
            except ValueError:
                num = None

            if isinstance(sounds, list):
                if num and num > 0 and num <= len(sounds):
                    sound = sounds[num - 1]

                elif message[1]:
                    searching = message[1].startswith("?")
                    search = message[1][1:] if searching else message[1]
                    sound = None
                    names = []
                    matches = []
                    for sound in sounds:
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

                        sound = matches[0][1]
                        if len(matches) > 1:
                            self.torchlight.SayPrivate(
                                player, "Multiple matches: {}".format(", ".join(mlist))
                            )

                    if not sound and not num:
                        if not searching:
                            self.torchlight.SayPrivate(
                                player,
                                "Couldn't find {} in list of sounds.".format(
                                    message[1]
                                ),
                            )
                        self.torchlight.SayPrivate(player, ", ".join(names))
                        return 1

                elif num:
                    self.torchlight.SayPrivate(
                        player,
                        f"Number {num} is out of bounds, max {len(sounds)}.",
                    )
                    return 1

                else:
                    sound = random.choice(sounds)
            else:
                sound = sounds

        if not sound:
            return 1

        os_path = os.path.abspath(os.path.join("sounds", sound))
        audio_clip = self.audio_manager.AudioClip(player, "file://" + os_path)
        if not audio_clip:
            return 1

        return audio_clip.Play()


class YouTube(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = ["!yt"]
        self.level = self.torchlight.config["CommandLevel"]["Youtube"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        if self.torchlight.last_url:
            message[1] = message[1].replace("!last", self.torchlight.last_url)

        temp_pos: int = -1
        real_time = None

        if (
            (temp_pos := message[1].find("&t=")) != -1
            or (temp_pos := message[1].find("?t=")) != -1
            or (temp_pos := message[1].find("#t=")) != -1
        ):
            time_str = (
                message[1][temp_pos + 3 :].split("&")[0].split("?")[0].split("#")[0]
            )
            if time_str:
                real_time = Utils.ParseTime(time_str)

        audio_clip = self.audio_manager.AudioClip(player, message[1])
        if not audio_clip:
            return 1

        return audio_clip.Play(real_time)


class YouTubeSearch(BaseCommand):
    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = ["!yts"]
        self.level = self.torchlight.config["CommandLevel"]["YoutubeSearch"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        temp_pos: int = -1
        real_time = None

        if (
            (temp_pos := message[1].find("&t=")) != -1
            or (temp_pos := message[1].find("?t=")) != -1
            or (temp_pos := message[1].find("#t=")) != -1
        ):
            time_str = (
                message[1][temp_pos + 3 :].split("&")[0].split("?")[0].split("#")[0]
            )
            if time_str:
                real_time = Utils.ParseTime(time_str)
            message[1] = message[1][:temp_pos]

        subprocess = await asyncio.create_subprocess_exec(
            "youtube-dl",
            "--dump-json",
            "-xg",
            "ytsearch:" + message[1],
            stdout=asyncio.subprocess.PIPE,
        )
        output, _ = await subprocess.communicate()

        try:
            url_raw, info = output.split(b"\n", maxsplit=1)
            url = url_raw.strip().decode("ascii")
        except Exception as e:
            self.logger.error(f"Failed to extract url from output: {str(output)}")
            self.logger.error(e)
            self.torchlight.SayPrivate(
                player,
                "An error as occured while trying to retrieve the youtube result.",
            )
            return 1

        json_info: dict[str, Any] = json.loads(info)

        if json_info["extractor_key"] == "Youtube":
            self.torchlight.SayChat(
                "{{darkred}}[YouTube]{{default}} {0} | {1} | {2:,}".format(
                    json_info["title"],
                    str(datetime.timedelta(seconds=json_info["duration"])),
                    int(json_info["view_count"]),
                )
            )

        audio_clip = self.audio_manager.AudioClip(player, url)
        if not audio_clip:
            return 1

        self.torchlight.last_url = url

        return audio_clip.Play(real_time)


class Say(BaseCommand):

    try:
        VALID_LANGUAGES = [lang for lang in gtts.lang.tts_langs().keys()]
    except Exception:
        VALID_LANGUAGES = [
            "af",
            "ar",
            "bn",
            "bs",
            "ca",
            "cs",
            "cy",
            "da",
            "de",
            "el",
            "en",
            "eo",
            "es",
            "et",
            "fi",
            "fr",
            "gu",
            "hi",
            "hr",
            "hu",
            "hy",
            "id",
            "is",
            "it",
            "ja",
            "jw",
            "km",
            "kn",
            "ko",
            "la",
            "lv",
            "mk",
            "ml",
            "mr",
            "my",
            "ne",
            "nl",
            "no",
            "pl",
            "pt",
            "ro",
            "ru",
            "si",
            "sk",
            "sq",
            "sr",
            "su",
            "sv",
            "sw",
            "ta",
            "te",
            "th",
            "tl",
            "tr",
            "uk",
            "ur",
            "vi",
            "zh-CN",
            "zh-TW",
            "zh",
        ]

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
    ) -> None:
        super().__init__(torchlight, access_manager, player_manager, audio_manager)
        self.triggers = [("!say", 4)]
        self.level = self.torchlight.config["CommandLevel"]["Say"]

    async def Say(self, player: Player, language: str, message: str) -> int:
        google_text_to_speech = gtts.gTTS(text=message, lang=language, lang_check=False)

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        google_text_to_speech.write_to_fp(temp_file)
        temp_file.close()

        audio_clip = self.audio_manager.AudioClip(player, "file://" + temp_file.name)
        if not audio_clip:
            os.unlink(temp_file.name)
            return 1

        if audio_clip.Play():
            audio_clip.audio_player.AddCallback(
                "Stop", lambda: os.unlink(temp_file.name)
            )
            return 0
        else:
            os.unlink(temp_file.name)
            return 1

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        if not message[1]:
            return 1

        language = "en"
        if len(message[0]) > 4:
            language = message[0][4:]

        self.logger.debug(f"{language}: {self.VALID_LANGUAGES}")
        if language not in self.VALID_LANGUAGES:
            return 1

        asyncio.ensure_future(self.Say(player, language, message[1]))
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
        self.triggers = ["!dec"]
        self.level = self.torchlight.config["CommandLevel"]["Dec"]

    async def Say(self, player: Player, message: str) -> int:
        message = "[:phoneme on]" + message
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        subprocess = await asyncio.create_subprocess_exec(
            "./say",
            "-fo",
            temp_file.name,
            cwd="dectalk",
            stdin=asyncio.subprocess.PIPE,
        )
        await subprocess.communicate(message.encode("utf-8", errors="ignore"))

        audio_clip = self.audio_manager.AudioClip(player, "file://" + temp_file.name)
        if not audio_clip:
            os.unlink(temp_file.name)
            return 1

        if audio_clip.Play(None, "-af", "volume=10dB"):
            audio_clip.audio_player.AddCallback(
                "Stop", lambda: os.unlink(temp_file.name)
            )
            return 0
        else:
            os.unlink(temp_file.name)
            return 1

        return 0

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

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
        self.triggers = ["!stop"]
        self.level = self.torchlight.config["CommandLevel"]["Stop"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

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
        self.triggers = ["!enable", "!disable"]
        self.level = self.torchlight.config["CommandLevel"]["Enable"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

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
            else:
                self.torchlight.SayChat("Torchlight is already enabled.")

        elif message[0] == "!disable":
            if not self.torchlight.disabled:
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
            else:
                self.torchlight.SayChat("Torchlight is already disabled.")

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
        self.triggers = ["!access"]
        self.level: int = self.torchlight.config["CommandLevel"]["AccessAdmin"]

    def ReloadValidUsers(self) -> None:
        self.access_manager.Load()
        for player in self.player_manager.players:
            if player:
                player.access = self.access_manager.get_access(player)

    async def _func(self, message: list[str], admin_player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))
        if not message[1]:
            return -1

        if message[1].lower() == "reload":
            self.ReloadValidUsers()
            self.torchlight.SayChat(
                "Loaded access list with {} users".format(
                    len(self.access_manager.config_access_list)
                )
            )

        elif message[1].lower() == "save":
            self.access_manager.Save()
            self.torchlight.SayChat(
                "Saved access list with {} users".format(
                    len(self.access_manager.config_access_list)
                )
            )

        # Modify access
        else:
            targeted_player: Player | None = None
            buffer = message[1]
            temp_buffer = buffer.find(" as ")
            if temp_buffer != -1:
                try:
                    reg_name, level_parsed = buffer[temp_buffer + 4 :].rsplit(" ", 1)
                except ValueError as e:
                    self.torchlight.SayChat(str(e))
                    return 1

                reg_name = reg_name.strip()
                level_parsed = level_parsed.strip()
                buffer = buffer[:temp_buffer].strip()
            else:
                try:
                    buffer, level_parsed = buffer.rsplit(" ", 1)
                except ValueError as e:
                    self.torchlight.SayChat(str(e))
                    return 2

                buffer = buffer.strip()
                level_parsed = level_parsed.strip()

            self.logger.info(f"Searching {buffer} to set his level to {level_parsed}")

            # Find user by User ID
            if buffer[0] == "#" and buffer[1:].isnumeric():
                targeted_player = self.player_manager.FindUserID(int(buffer[1:]))
            # Search user by name
            else:
                for player in self.player_manager.players:
                    if player and player.name.lower().find(buffer.lower()) != -1:
                        targeted_player = player
                        break

            if targeted_player is None:
                self.torchlight.SayChat(f"Couldn't find user: {buffer}")
                return 3

            if level_parsed.isnumeric() or (
                level_parsed.startswith("-") and level_parsed[1:].isdigit()
            ):
                level = int(level_parsed)

                if level >= admin_player.access.level:
                    self.torchlight.SayChat(
                        "Trying to assign level {}, which is higher or equal than your level ({})".format(
                            level, admin_player.access.level
                        )
                    )
                    return 4

                if (
                    targeted_player.access.level >= admin_player.access.level
                    and admin_player.user_id != targeted_player.user_id
                ):
                    self.torchlight.SayChat(
                        "Trying to modify level {}, which is higher or equal than your level ({})".format(
                            targeted_player.access.level,
                            admin_player.access.level,
                        )
                    )
                    return 5

                if "Regname" in locals():
                    self.torchlight.SayChat(
                        'Changed "{}"({}) as {} level/name from {} to {} as {}'.format(
                            targeted_player.name,
                            targeted_player.unique_id,
                            targeted_player.access.name,
                            targeted_player.access.level,
                            level,
                            reg_name,
                        )
                    )
                    targeted_player.access.name = reg_name
                else:
                    self.torchlight.SayChat(
                        'Changed "{}"({}) as {} level from {} to {}'.format(
                            targeted_player.name,
                            targeted_player.unique_id,
                            targeted_player.access.name,
                            targeted_player.access.level,
                            level,
                        )
                    )

                targeted_player.access.level = level
                self.access_manager.config_access_list[
                    targeted_player.unique_id
                ] = targeted_player.access
            else:
                if level_parsed == "revoke":
                    if targeted_player.access.level >= admin_player.access.level:
                        self.torchlight.SayChat(
                            "Trying to revoke level {}, which is higher or equal than your level ({})".format(
                                targeted_player.access.level,
                                admin_player.access.level,
                            )
                        )
                        return 6

                    self.torchlight.SayChat(
                        'Removed "{}"({}) from access list (was {} with level {})'.format(
                            targeted_player.name,
                            targeted_player.unique_id,
                            targeted_player.access.name,
                            targeted_player.access.level,
                        )
                    )
                    targeted_player.access.name = "Player"
                    targeted_player.access.level = self.torchlight.config[
                        "AccessLevel"
                    ]["Player"]
                    targeted_player.access.uniqueid = targeted_player.unique_id
                    self.access_manager.config_access_list[
                        targeted_player.unique_id
                    ] = targeted_player.access
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
        self.triggers = ["!reload"]
        self.level = self.torchlight.config["CommandLevel"]["Reload"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))
        self.torchlight.Reload()
        self.torchlight.SayPrivate(
            message="Torchlight has been reloaded", player=player
        )
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
        self.triggers = ["!exec"]
        self.level = self.torchlight.config["CommandLevel"]["Exec"]

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))
        try:
            resp = eval(message[1])
        except Exception as e:
            self.torchlight.SayChat(f"Error: {str(e)}")
            return 1
        self.torchlight.SayChat(str(resp))
        return 0
