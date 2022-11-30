#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import logging

import click

from torchlight.Config import Config
from torchlight.SourceRCONServer import SourceRCONServer
from torchlight.TorchlightHandler import TorchlightHandler


@click.command()
@click.option('--config-folder', default="config", help='Configuration folder path.')
@click.option('-v', '--verbose', count=True, help="Verbosity level")
def cli(config_folder: str, verbose: int) -> None:

    log_level = logging.ERROR
    if verbose > 2:
        log_level = logging.DEBUG
    elif verbose > 1:
        log_level = logging.INFO
    elif verbose > 0:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z',
    )

    Loop = asyncio.get_event_loop()

    config = Config(config_folder)

    TorchHandler = TorchlightHandler(Loop, config)

    # Handles new connections on 0.0.0.0:27015
    RCONServer = SourceRCONServer(
        config["TorchRCON"],
        TorchHandler,
    )

    # Run!
    Loop.run_forever()
