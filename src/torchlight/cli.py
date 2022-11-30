#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import gc
import logging

import click
from SourceRCONServer import SourceRCONServer
from Torchlight import TorchlightHandler

TorchMaster: TorchlightHandler


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

    global TorchMaster
    TorchMaster = TorchlightHandler(Loop)

    # Handles new connections on 0.0.0.0:27015
    RCONConfig = TorchMaster.Config["TorchRCON"]
    RCONServer = SourceRCONServer(
        Loop,
        TorchMaster,
        Host=RCONConfig["Host"],
        Port=RCONConfig["Port"],
        Password=RCONConfig["Password"],
    )

    # Run!
    Loop.run_forever()
