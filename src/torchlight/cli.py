import asyncio
import logging

import click

from torchlight.Config import Config
from torchlight.SourceRCONServer import SourceRCONServer
from torchlight.TorchlightHandler import TorchlightHandler

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--config-folder", default="config", help="Configuration folder path."
)
@click.version_option()
def cli(config_folder: str) -> None:

    config = Config(config_folder)

    logging.basicConfig(
        level=logging.getLevelName(config["Logging"]["level"]),
        format=config["Logging"]["format"],
        datefmt=config["Logging"]["datefmt"],
    )

    event_loop = asyncio.get_event_loop()

    torchlight_handler = TorchlightHandler(event_loop, config)

    # Handles new connections on 0.0.0.0:27015
    rcon_server = SourceRCONServer(
        config["TorchRCON"],
        torchlight_handler,
    )
    asyncio.Task(rcon_server._server())

    # Run!
    event_loop.run_forever()
