import asyncio
import logging
import signal
from types import FrameType

import click

from torchlight.Config import Config, ConfigError
from torchlight.SourceRCONServer import SourceRCONServer
from torchlight.TorchlightHandler import TorchlightHandler
from torchlight.Utils import Utils

logger = logging.getLogger(__name__)

# Upper bound for the work scheduled by the teardown (ffmpeg terminate/kill, socket and
# session closes) to finish before the loop stops. _reap_process() waits 2s before kill().
SHUTDOWN_GRACE_SECONDS = 3.0
SHUTDOWN_TEARDOWN_TIMEOUT = 5.0


async def shutdown(
    loop: asyncio.AbstractEventLoop,
    torchlight_handler: TorchlightHandler,
    rcon_task: asyncio.Task,
) -> None:
    rcon_task.cancel()

    current = asyncio.current_task()
    tasks_before = asyncio.all_tasks()

    try:
        await asyncio.wait_for(torchlight_handler.Shutdown(), timeout=SHUTDOWN_TEARDOWN_TIMEOUT)
    except Exception:
        logger.exception("Teardown failed")

    # FFmpegAudioPlayer.Stop() only schedules the ffmpeg reaping (via call_soon_threadsafe),
    # so yield once for those tasks to exist, then give them a bounded chance to finish.
    await asyncio.sleep(0)
    spawned = asyncio.all_tasks() - tasks_before - {current}
    if spawned:
        _, pending = await asyncio.wait(spawned, timeout=SHUTDOWN_GRACE_SECONDS)
        if pending:
            logger.warning(f"{len(pending)} teardown task(s) still pending after {SHUTDOWN_GRACE_SECONDS}s")

    # Not in a finally: if a second signal already stopped the loop, close_loop() cancels this
    # task, and stopping again inside its run_until_complete() would abort that cleanup.
    loop.stop()


def close_loop(loop: asyncio.AbstractEventLoop) -> None:
    # Like asyncio.run(): cancel what is left, then release the loop (close() shuts the
    # default executor down without waiting on a blocked yt-dlp/curl thread).
    try:
        remaining = asyncio.all_tasks(loop)
        for task in remaining:
            task.cancel()
        if remaining:
            loop.run_until_complete(asyncio.gather(*remaining, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@click.command()
@click.option("--config-folder", default="config", help="Configuration folder path.")
@click.version_option()
def cli(config_folder: str) -> None:
    config = Config(config_folder)

    # A malformed or missing config file aborts startup with the offending path and
    # parse error rather than silently starting with an empty config (see issue #164).
    try:
        config.load()
    except ConfigError as e:
        raise click.ClickException(str(e)) from e

    logging.basicConfig(
        level=logging.getLevelName(config["Logging"]["level"]),
        format=config["Logging"]["format"],
        datefmt=config["Logging"]["datefmt"],
    )

    # Explicit loop: TorchlightHandler schedules its first connection from __init__, before
    # run_forever(), and implicit loop creation by get_event_loop() is deprecated.
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)

    try:
        torchlight_handler = TorchlightHandler(event_loop, config)

        # Handles new connections on 0.0.0.0:27015
        rcon_server = SourceRCONServer(
            config["TorchRCON"],
            torchlight_handler,
        )
    except BaseException as e:
        close_loop(event_loop)
        if isinstance(e, ConfigError):
            raise click.ClickException(str(e)) from e
        raise

    # The loop only keeps weak references to tasks: hold this one for the process lifetime.
    rcon_task = Utils.FireAndForget(rcon_server._server(), logger)

    shutdown_task: asyncio.Task | None = None

    def request_shutdown() -> None:
        nonlocal shutdown_task
        if shutdown_task is not None:
            logger.warning("Shutdown already in progress, stopping now")
            event_loop.stop()
            return
        logger.info("Stop signal received, shutting down")
        shutdown_task = event_loop.create_task(shutdown(event_loop, torchlight_handler, rcon_task))

    def signal_fallback(signum: int, frame: FrameType | None) -> None:
        event_loop.call_soon_threadsafe(request_shutdown)

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            event_loop.add_signal_handler(signum, request_shutdown)
        except NotImplementedError:
            # Windows event loops have no add_signal_handler(); a plain handler that hands
            # over to the loop still runs the async teardown before stopping it.
            signal.signal(signum, signal_fallback)

    # Run!
    try:
        event_loop.run_forever()
    finally:
        close_loop(event_loop)
        rcon_server._serv_sock.close()
