import logging
import os

import geoip2.database

logger = logging.getLogger(__name__)

# Cached per database path as (mtime, reader). Kept at module level - and in this
# module rather than in Commands.py - so it survives importlib.reload(Commands)
# when the bot processes a !reload.
_readers: dict[str, tuple[float, geoip2.database.Reader]] = {}


def _close_quietly(reader: geoip2.database.Reader) -> None:
    try:
        reader.close()
    except Exception:
        logger.debug("Failed to close previous GeoIP reader", exc_info=True)


def get_city_reader(database_path: str) -> geoip2.database.Reader:
    """Open the GeoIP city database once and reuse it across reloads.

    ``CommandHandler.Setup`` rebuilds every command whenever the configuration is
    reloaded. Opening a fresh :class:`geoip2.database.Reader` each time leaked the
    previous memory map of the database until garbage collection (issue #55) and
    could then fail to map the file at all, breaking command setup (issue #174).

    The database is read-only, so a single reader is kept per path and only
    reopened when the file on disk changes (for instance after a GeoIP update).
    """
    cached = _readers.get(database_path)

    try:
        mtime = os.path.getmtime(database_path)
    except OSError:
        if cached is not None:
            return cached[1]
        raise

    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        reader = geoip2.database.Reader(database_path)
    except Exception:
        if cached is not None:
            # A refreshed database file is momentarily unreadable; keep serving
            # the reader we already have instead of losing GeoIP entirely.
            logger.warning(f"Could not reopen GeoIP database {database_path}, keeping the previous reader")
            return cached[1]
        raise

    if cached is not None:
        _close_quietly(cached[1])
    _readers[database_path] = (mtime, reader)
    logger.info(f"Opened GeoIP database {database_path}")
    return reader
