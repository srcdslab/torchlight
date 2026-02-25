import ast
import asyncio
import datetime
import logging
import os
import re
import secrets
import sys
import tempfile
import traceback
from pathlib import Path
from re import Match, Pattern
from typing import Any

import aiohttp
import defusedxml.ElementTree as etree
import geoip2.database
import gtts

from torchlight.AccessManager import AccessManager
from torchlight.AudioManager import AudioManager
from torchlight.Config import Config
from torchlight.Player import Player
from torchlight.PlayerManager import PlayerManager
from torchlight.Torchlight import Torchlight
from torchlight.TriggerManager import TriggerManager
from torchlight.URLInfo import (
    get_audio_format,
    get_first_valid_entry,
    get_url_real_time,
    get_url_text,
    get_url_youtube_info,
    print_url_metadata,
)


class BaseCommand:
    order = 0

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
        trigger_manager: TriggerManager,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torchlight = torchlight
        self.audio_manager = audio_manager
        self.player_manager = player_manager
        self.access_manager = access_manager
        self.trigger_manager = trigger_manager
        self.triggers: list[tuple[str, int] | str | Pattern] = []
        self.level = 0
        self.random_trigger_name: str | None = None

        self.init_command()

    def get_config(self) -> dict[str, Any]:
        return self.torchlight.config["Command"][self.command_name()]

    def init_command(self) -> None:
        command_config = self.get_config()
        self.level = command_config["level"]
        if "triggers" in command_config:
            for trigger in command_config["triggers"]:
                command = trigger["command"]
                if "starts_with" in trigger and trigger["starts_with"]:
                    self.triggers.append((command, len(command)))
                else:
                    self.triggers.append(command)

    def command_name(self) -> str:
        return self.__class__.__name__

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
        level = player.admin.level

        disabled = self.torchlight.disabled
        if disabled and (
            disabled > level or disabled == level and level < self.torchlight.config["AntiSpam"]["ImmunityLevel"]
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

    youtube_regex = re.compile(
        r".*?(?:youtube\.com\/\S*(?:(?:\/e(?:mbed))?\/|watch\?(?:\S*?&?v\=))|youtu\.be\/)([a-zA-Z0-9_-]{6,11}).*?"
    )

    def __init__(
        self,
        torchlight: Torchlight,
        access_manager: AccessManager,
        player_manager: PlayerManager,
        audio_manager: AudioManager,
        trigger_manager: TriggerManager,
    ) -> None:
        super().__init__(
            torchlight,
            access_manager,
            player_manager,
            audio_manager,
            trigger_manager,
        )
        self.triggers = [
            re.compile(
                r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""",
                re.IGNORECASE,
            )
        ]
        self.level: int = -1

    async def URLInfo(self, url: str) -> None:
        try:
            await print_url_metadata(url=url, callback=self.torchlight.SayChat)
        except Exception as e:
            self.torchlight.SayChat(f"Error: {str(e)}")
            self.logger.error(traceback.format_exc())

        self.torchlight.last_url = url

    async def URLText(self, url: str) -> str:
        text = ""

        try:
            text = await get_url_text(url=url)
        except Exception as e:
            self.torchlight.SayChat(f"Error: {str(e)}")
            self.logger.error(traceback.format_exc())

        self.torchlight.last_url = url
        return text

    async def _rfunc(self, line: str, match: Match, player: Player) -> str | int:
        url: str = match.groups()[0]
        if not url.startswith("http") and not url.startswith("ftp"):
            url = "http://" + url

        if line.startswith("!yts ") or line.startswith("!yt "):
            return line

        if line.startswith("!dec "):
            text = await self.URLText(url)
            if len(text) > 0:
                return "!dec " + text

        asyncio.ensure_future(self.URLInfo(url))
        return -1


def FormatAccess(config: Config, player: Player) -> str:
    answer = f'#{player.user_id} "{player.name}"({player.unique_id}) is '
    level = str(player.admin.level)
    answer += f"level {level!s} as {player.admin.name}."

    if level in config["AudioLimits"]:
        uses = config["AudioLimits"][level]["Uses"]
        total_time = config["AudioLimits"][level]["TotalTime"]

        if uses >= 0:
            answer += " Uses: {}/{}".format(player.storage["Audio"]["Uses"], uses)
        if total_time >= 0:
            answer += " Time: {}/{}".format(
                round(player.storage["Audio"]["TimeUsed"], 2),
                round(total_time, 2),
            )

    return answer


class Access(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if message[0] == "!access":
            if message[1]:
                return -1

            self.torchlight.SayChat(FormatAccess(self.torchlight.config, player), player)

        return 0


class Who(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        Count = 0
        if message[0] == "!who":
            for targeted_player in self.player_manager.players:
                if targeted_player and message[1].lower() in targeted_player.name.lower():
                    self.torchlight.SayChat(FormatAccess(self.torchlight.config, targeted_player))

                    Count += 1
                    if Count >= 3:
                        break

        elif message[0] == "!whois":
            for admin in self.access_manager.admins:
                if message[1].lower() in admin.name.lower():
                    targeted_player = self.player_manager.FindUniqueID(admin.unique_id)
                    if targeted_player is not None:
                        self.torchlight.SayChat(FormatAccess(self.torchlight.config, targeted_player))
                    else:
                        self.torchlight.SayChat(
                            f'#? "{admin.name}"({admin.unique_id}) is level {admin.level!s} is currently offline.'
                        )

                    Count += 1
                    if Count >= 3:
                        break
        return 0


class WolframAlpha(BaseCommand):
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
                    "http://api.wolframalpha.com/v2/query",
                    params=parameters_json,
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
                [p.text.strip() for p in root.findall(".//subpod/plaintext") if p is not None and p.text is not None],
            )
        )

        # no answer pods found, check if there are didyoumeans-elements
        if not pods:
            did_you_means = root.find("didyoumeans")
            # no support for future stuff yet, TODO?
            if not did_you_means:
                # If there's no pods, the question clearly wasn't understood
                self.torchlight.SayChat("Sorry, couldn't understand the question.", player)
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
            {
                "input": message[1],
                "appid": self.torchlight.config["WolframAPIKey"],
            }
        )
        ret = await self.Calculate(parameters_json, player)
        return ret


class UrbanDictionary(BaseCommand):
    # @profile
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_chat_cooldown(player):
            return -1

        if self.check_disabled(player):
            return -1

        async with aiohttp.ClientSession() as session:
            resp = await asyncio.wait_for(
                session.get(f"https://api.urbandictionary.com/v0/define?term={message[1]}"),
                5,
            )
            if not resp:
                return 1

            data = await asyncio.wait_for(resp.json(), 5)
            if not data:
                return 3

            if "list" not in data or not data["list"]:
                self.torchlight.SayChat(f"[UB] No definition found for: {message[1]}", player)
                return 4

            def print_item(item: dict[str, Any]) -> None:
                self.torchlight.SayChat(
                    "[UD] {word} ({thumbs_up}/{thumbs_down}): {definition}\n{example}".format(**item),
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
        trigger_manager: TriggerManager,
    ) -> None:
        super().__init__(
            torchlight,
            access_manager,
            player_manager,
            audio_manager,
            trigger_manager,
        )
        self.config_folder = self.torchlight.config["GeoIP"]["Path"]
        self.city_filename = self.torchlight.config["GeoIP"]["CityFilename"]
        self.geo_ip = geoip2.database.Reader(f"{self.config_folder}/{self.city_filename}")

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
            search = f"lat={info.location.latitude}&lon={info.location.longitude}"
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

        timezone = "{}{}".format("+" if data["timezone"] > 0 else "", int(data["timezone"] / 3600))
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
                    session.get(f"http://autocomplete.wunderground.com/aq?format=JSON&query={message[1]}"),
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
                self.torchlight.SayPrivate(player, "[WU] No cities match your search query.")
                return 4

            search = data["RESULTS"][0]["name"]
            additional = ""

        async with aiohttp.ClientSession() as session:
            resp = await asyncio.wait_for(
                session.get(
                    "http://api.wunderground.com/api/{}/conditions/q/{}.json{}".format(
                        self.torchlight.config["WundergroundAPIKey"],
                        search,
                        additional,
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
                player,
                "[WU] {}.".format(data["response"]["error"]["description"]),
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
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.torchlight.disabled:
            self.torchlight.SayPrivate(
                player,
                "Torchlight is already disabled for the duration of this map.",
            )
            return -1

        self.torchlight.disable_votes.add(player.unique_id)

        have = len(self.torchlight.disable_votes)
        needed = self.player_manager.player_count // 5
        if have >= needed:
            self.torchlight.SayChat("Torchlight has been disabled for the duration of this map.")
            self.torchlight.disabled = 6
        else:
            self.torchlight.SayPrivate(
                player,
                f"Torchlight needs {needed - have} more disable votes to be disabled.",
            )

        return 0


class VoiceTrigger(BaseCommand):
    def _setup(self) -> None:
        self.logger.debug(sys._getframe().f_code.co_name)
        for trigger in self.trigger_manager.voice_triggers.keys():
            self.triggers.append(trigger)

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        voice_trigger = message[0].lower()
        trigger_number = message[1].lower()

        sound = self.get_sound_path(
            player=player,
            voice_trigger=voice_trigger,
            trigger_number=trigger_number,
        )

        if not sound:
            return 1

        sound_path = os.path.abspath(
            os.path.join(
                self.trigger_manager.sound_path,
                sound,
            )
        )
        audio_clip = self.audio_manager.AudioClip(player, Path(sound_path).absolute().as_uri())
        if not audio_clip:
            return 1

        if self.random_trigger_name:
            self.torchlight.SayChat(f"Now playing {{olive}}{self.random_trigger_name}")

        return audio_clip.Play()

    def get_sound_path(self, player: Player, voice_trigger: str, trigger_number: str) -> str | None:
        level = player.admin.level

        if voice_trigger[0] != "!" and level < self.torchlight.config["Command"]["VoiceTriggerReserved"]["level"]:
            return None

        sound = None

        sounds = self.trigger_manager.voice_triggers[voice_trigger]

        try:
            num = int(trigger_number)
        except ValueError:
            num = None

        if isinstance(sounds, list):
            if num and num > 0 and num <= len(sounds):
                sound = sounds[num - 1]

            elif trigger_number:
                searching = trigger_number.startswith("?")
                search = trigger_number[1:] if searching else trigger_number
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
                        return None

                    sound = matches[0][1]
                    if len(matches) > 1:
                        self.torchlight.SayPrivate(
                            player,
                            "Multiple matches: {}".format(", ".join(mlist)),
                        )

                if not sound and not num:
                    if not searching:
                        self.torchlight.SayPrivate(
                            player,
                            f"Couldn't find {trigger_number} in list of sounds.",
                        )
                    self.torchlight.SayPrivate(player, ", ".join(names))
                    return None

            elif num:
                self.torchlight.SayPrivate(
                    player,
                    f"Number {num} is out of bounds, max {len(sounds)}.",
                )
                return None

            else:
                sound = secrets.choice(sounds)
        else:
            sound = sounds

        return sound


class Random(VoiceTrigger):
    def get_sound_path(self, player: Player, voice_trigger: str, trigger_number: str) -> str | None:
        trigger_name, trigger = secrets.choice(list(self.trigger_manager.voice_triggers.items()))

        self.random_trigger_name = trigger_name

        if isinstance(trigger, list):
            return secrets.choice(trigger)
        return trigger


class Search(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        voice_trigger = message[1].lower()

        res = []
        for key in self.trigger_manager.voice_triggers.keys():
            if voice_trigger in key.lower():
                res.append(key)
        self.torchlight.SayPrivate(player, "{} results: {}".format(len(res), ", ".join(res)))
        return 0


class PlayMusic(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        if self.torchlight.last_url:
            message[1] = message[1].replace("!last", self.torchlight.last_url)

        url = message[1]

        real_time = get_url_real_time(url=url)
        audio_clip = self.audio_manager.AudioClip(player, url)
        if not audio_clip:
            return 1

        return audio_clip.Play(real_time)


class YouTubeSearch(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        command_config = self.get_config()

        input_keywords = message[1]
        if URLFilter.youtube_regex.search(input_keywords):
            input_url = input_keywords
        else:
            input_url = f"ytsearch3: {input_keywords}"

        real_time = get_url_real_time(url=input_url)

        proxy = command_config.get("parameters", {}).get("proxy", "")

        try:
            info = get_url_youtube_info(url=input_url, proxy=proxy)
        except Exception as exc:
            self.logger.error(f"Failed to extract youtube info from: {input_url}")
            self.logger.error(exc)
            self.torchlight.SayPrivate(
                player,
                "An error as occured while trying to retrieve youtube metadata.",
            )
            return 1

        if "title" not in info and "url" in info:
            info = get_url_youtube_info(url=info["url"], proxy=proxy)
        if info["extractor_key"] == "YoutubeSearch":
            info = get_first_valid_entry(entries=info["entries"], proxy=proxy)

        title = info["title"]
        url = get_audio_format(info=info)
        title_words = title.split()
        keywords_banned: list[str] = []

        if "parameters" in command_config and "keywords_banned" in command_config["parameters"]:
            keywords_banned = command_config["parameters"]["keywords_banned"]

        for keyword_banned in keywords_banned:
            for title_word in title_words:
                if keyword_banned.lower() in title_word.lower():
                    self.torchlight.SayChat(
                        f"{{darkred}}[YouTube]{{default}} {title} has been flagged as inappropriate content, skipping"
                    )
                    return 1

        duration = str(datetime.timedelta(seconds=info["duration"]))
        views = int(info["view_count"])
        self.torchlight.SayChat(f"{{darkred}}[YouTube]{{default}} {title} | {duration} | {views}")

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

    async def Say(self, player: Player, language: str, tld: str, message: str) -> int:
        google_text_to_speech = gtts.gTTS(text=message, tld=tld, lang=language, lang_check=False)

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        google_text_to_speech.write_to_fp(temp_file)
        temp_file.close()

        audio_clip = self.audio_manager.AudioClip(player, Path(temp_file.name).absolute().as_uri())
        if not audio_clip:
            os.unlink(temp_file.name)
            return 1

        if audio_clip.Play():
            audio_clip.audio_player.AddCallback("Stop", lambda: os.unlink(temp_file.name))
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

        language: str = ""
        tld: str = "com"

        command_config = self.get_config()
        if "parameters" in command_config and "default" in command_config["parameters"]:
            if "language" in command_config["parameters"]["default"]:
                language = command_config["parameters"]["default"]["language"]
            if "tld" in command_config["parameters"]["default"]:
                tld = command_config["parameters"]["default"]["tld"]

        if len(message[0]) > 4:
            language = message[0][4:]

        self.logger.debug(f"{language}: {self.VALID_LANGUAGES}")
        if len(language) <= 0 or language not in self.VALID_LANGUAGES:
            return 1

        asyncio.ensure_future(self.Say(player, language, tld, message[1]))
        return 0


class DECTalk(BaseCommand):
    async def Say(self, player: Player, message: str) -> int:
        message = "[:phoneme on]" + message
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        dectalk_path = os.path.abspath(self.torchlight.config.config.get("DECTalk", {}).get("Path", "dectalk"))
        dectalk_say_path = os.path.abspath(
            os.path.join(
                dectalk_path,
                self.torchlight.config.config.get("DECTalk", {}).get("SayFilename", "say"),
            )
        )
        subprocess = await asyncio.create_subprocess_exec(
            dectalk_say_path,
            "-fo",
            temp_file.name,
            cwd=dectalk_path,
            stdin=asyncio.subprocess.PIPE,
        )
        await subprocess.communicate(message.encode("utf-8", errors="ignore"))

        audio_clip = self.audio_manager.AudioClip(player, Path(temp_file.name).absolute().as_uri())
        if not audio_clip:
            os.unlink(temp_file.name)
            return 1

        if audio_clip.Play(None, "-af", "volume=10dB"):
            audio_clip.audio_player.AddCallback("Stop", lambda: os.unlink(temp_file.name))
            return 0

        os.unlink(temp_file.name)
        return 1

    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.check_disabled(player):
            return -1

        if not message[1]:
            return 1

        asyncio.ensure_future(self.Say(player, message[1]))
        return 0


class Stop(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        self.audio_manager.Stop(player, message[1])
        return True


class Enable(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))

        if self.torchlight.disabled:
            if self.torchlight.disabled > player.admin.level:
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

        return 0


class Disable(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        if not self.torchlight.disabled:
            if self.torchlight.disabled > player.admin.level:
                self.torchlight.SayPrivate(
                    player,
                    (
                        "You don't have access to disable torchlight"
                        ", since it was already disabled by a higher level user."
                    ),
                )
                return 1
            self.torchlight.SayChat(
                "Torchlight has been disabled for the duration of this map - Type !enable to enable it again."
            )
            self.torchlight.disabled = player.admin.level
        else:
            self.torchlight.SayChat("Torchlight is already disabled.")
        return 0


class AdminAccess(BaseCommand):
    def ReloadValidUsers(self) -> None:
        self.access_manager.Load()
        for player in self.player_manager.players:
            if player:
                admin_override = self.access_manager.get_admin(unique_id=player.unique_id)
                if admin_override is not None:
                    self.logger.info(f"{player.unique_id}: overriding admin with {admin_override}")
                    player.admin = admin_override

    async def _func(self, message: list[str], admin_player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))
        if not message[1]:
            return -1

        if message[1].lower() == "reload":
            self.ReloadValidUsers()
            self.torchlight.SayChat(f"Loaded access list with {len(self.access_manager.admins)} users".format())

        elif message[1].lower() == "save":
            self.access_manager.Save()
            self.torchlight.SayChat(f"Saved access list with {len(self.access_manager.admins)} users".format())

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

            if level_parsed.isnumeric() or (level_parsed.startswith("-") and level_parsed[1:].isdigit()):
                level = int(level_parsed)

                if level >= admin_player.admin.level:
                    self.torchlight.SayChat(
                        f"Trying to assign level {level}"
                        f", which is higher or equal than your level ({admin_player.admin.level})"
                    )
                    return 4

                if (
                    targeted_player.admin.level >= admin_player.admin.level
                    and admin_player.user_id != targeted_player.user_id
                ):
                    self.torchlight.SayChat(
                        f"Trying to modify level {targeted_player.admin.level},"
                        f" which is higher or equal than your level ({admin_player.admin.level})"
                    )
                    return 5

                if "Regname" in locals():
                    self.torchlight.SayChat(
                        f'Changed "{targeted_player.name}"({targeted_player.unique_id})'
                        f" as {targeted_player.admin.name} level/name"
                        f" from {targeted_player.admin.level} to {level} as {reg_name}"
                    )
                    targeted_player.admin.name = reg_name
                else:
                    self.torchlight.SayChat(
                        f'Changed "{targeted_player.name}"({targeted_player.unique_id})'
                        f" as {targeted_player.admin.name} level"
                        f" from {targeted_player.admin.level} to {level}"
                    )

                targeted_player.admin.level = level
                self.access_manager.set_admin(
                    unique_id=targeted_player.unique_id,
                    admin=targeted_player.admin,
                )
            else:
                if level_parsed == "revoke":
                    if targeted_player.admin.level >= admin_player.admin.level:
                        self.torchlight.SayChat(
                            f"Trying to revoke level {targeted_player.admin.level}"
                            f", which is higher or equal than your level ({admin_player.admin.level})"
                        )
                        return 6

                    self.torchlight.SayChat(
                        f'Removed "{targeted_player.name}"({targeted_player.unique_id}) from access list '
                        f"(was {targeted_player.admin.name} with level {targeted_player.admin.level})"
                    )
                    targeted_player.admin.name = "Revoked"
                    targeted_player.admin.level = 0
                    targeted_player.admin.unique_id = targeted_player.unique_id
                    self.access_manager.set_admin(
                        unique_id=targeted_player.unique_id,
                        admin=targeted_player.admin,
                    )
        return 0


class Reload(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))
        self.torchlight.Reload()
        self.torchlight.SayPrivate(message="Torchlight has been reloaded", player=player)
        return 0


class Exec(BaseCommand):
    async def _func(self, message: list[str], player: Player) -> int:
        self.logger.debug(sys._getframe().f_code.co_name + " " + str(message))
        try:
            resp = ast.literal_eval(message[1])
        except Exception as e:
            self.torchlight.SayChat(f"Error: {str(e)}")
            return 1
        self.torchlight.SayChat(str(resp))
        return 0
