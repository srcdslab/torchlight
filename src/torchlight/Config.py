import json
import logging
import os
from collections import OrderedDict
from typing import Any


class ConfigError(Exception):
    """A config file is missing, unreadable or contains invalid JSON."""


class ConfigFile:
    """Resolves a config file path under the config folder and parses it as JSON."""

    def __init__(
        self,
        config_folder: str,
        config_filename: str,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_folder = os.path.abspath(config_folder)
        self.config_filename = config_filename
        self.config_filepath = os.path.abspath(os.path.join(config_folder, config_filename))

    def load_json(self, *, ordered: bool = False) -> Any:
        try:
            with open(self.config_filepath) as fp:
                if ordered:
                    return json.load(fp, object_pairs_hook=OrderedDict)
                return json.load(fp)
        except FileNotFoundError as e:
            raise ConfigError(f"{self.config_filepath}: config file not found") from e
        except OSError as e:
            raise ConfigError(f"{self.config_filepath}: cannot read config file ({e.strerror or e})") from e
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"{self.config_filepath}: invalid JSON on line {e.lineno}, column {e.colno} ({e.msg})"
            ) from e


class Config(ConfigFile):
    def __init__(
        self,
        config_folder: str,
        config_filename: str = "config.json",
    ) -> None:
        super().__init__(config_folder, config_filename)
        self.config: dict[str, Any] = {}

    def load(self) -> None:
        self.config = self.load_json()

    def __getitem__(self, key: str) -> Any:
        if key in self.config:
            return self.config[key]
        raise Exception(f"Key {key} not found in config")
