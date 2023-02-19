#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging

import click

from torchlight.Config import Config
from torchlight.SourceRCONServer import SourceRCONServer
from torchlight.TorchlightHandler import TorchlightHandler

logger = logging.getLogger(__name__)

@click.command()
@click.option('--config-folder', default="config", help='Configuration folder path.')
def cli(config_folder: str) -> None:

    config = Config(config_folder)

    logging.basicConfig(
        level=logging.getLevelName(config["Logging"]["level"]),
        format=config["Logging"]["format"],
        datefmt=config["Logging"]["datefmt"],
    )

    Loop = asyncio.get_event_loop()

    TorchHandler = TorchlightHandler(Loop, config)

    # Handles new connections on 0.0.0.0:27015
    RCONServer = SourceRCONServer(
        config["TorchRCON"],
        TorchHandler,
    )

    # Run!
    Loop.run_forever()
