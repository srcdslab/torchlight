import asyncio
import logging
import signal
import sys
from types import FrameType

import click

from torchlight.Config import Config
from torchlight.PlayerManager import PlayerManager
from torchlight.SourceRCONServer import SourceRCONServer
from torchlight.TorchlightHandler import TorchlightHandler

logger = logging.getLogger(__name__)


torchlight_handler: TorchlightHandler | None = None


def graceful_shutdown(signal: int, frame: FrameType | None) -> None:
    if torchlight_handler and torchlight_handler.audio_manager:
        logger.info("Stopping all audio sounds")
        player = PlayerManager.create_console_player()
        torchlight_handler.audio_manager.Stop(player, "")
    sys.exit(0)


@click.command()
@click.option("--config-folder", default="config", help="Configuration folder path.")
@click.version_option()
def cli(config_folder: str) -> None:
    config = Config(config_folder)
    config.load()

    logging.basicConfig(
        level=logging.getLevelName(config["Logging"]["level"]),
        format=config["Logging"]["format"],
        datefmt=config["Logging"]["datefmt"],
    )

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    event_loop = asyncio.get_event_loop()

    global torchlight_handler
    torchlight_handler = TorchlightHandler(event_loop, config)

    # Handles new connections on 0.0.0.0:27015
    rcon_server = SourceRCONServer(
        config["TorchRCON"],
        torchlight_handler,
    )
    asyncio.Task(rcon_server._server())

    # Run!
    event_loop.run_forever()
