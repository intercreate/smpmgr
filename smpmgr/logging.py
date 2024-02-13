"""Logging configuration for smpmgr."""

import asyncio
import logging
from enum import Enum, unique
from pathlib import Path
from typing import Dict

import click
import serial
import typer
from rich.logging import RichHandler


@unique
class LogLevel(Enum):
    CRITICAL = 'CRITICAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'
    NOTSET = 'NOTSET'


def setup_logging(loglevel: LogLevel | None, logfile: Path | None) -> None:
    """Setup logging for smpmgr.

    During normal operation, this function is called once at the start of the program.  However,
    when using the `shell` command, this function may be called multiple times.  This allows the
    user to change the log level and log file without restarting the program.

    For example, to change the log level to DEBUG and the log file to `smpmgr.log`:

    ```shell
    smpmgr > --loglevel DEBUG --logfile smpmgr.log
    ```
    This is a valid stand alone command that will save those log settings for the duration of the
    shell session, until one or the other is updated with new values.
    """

    DEBUG_FORMAT = "%(message)s - %(pathname)s:%(lineno)s"
    DEFAULT_FORMAT = "%(message)s - %(module)s:%(lineno)s"
    LOGFILE_FORMAT = "%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)s - %(message)s"
    NAME_CONSOLE_HANDLER = "console_handler"
    NAME_FILE_HANDLER = "file_handler"

    base_console_handler = RichHandler(
        rich_tracebacks=True, tracebacks_suppress=[click, typer, asyncio, serial]
    )
    base_console_handler.name = NAME_CONSOLE_HANDLER

    console_handler = (
        RichHandler(rich_tracebacks=True, tracebacks_suppress=[click, typer, asyncio, serial])
        if loglevel is not None
        else None
    )
    if console_handler is not None:
        console_handler.name = NAME_CONSOLE_HANDLER

    file_handler = logging.FileHandler(logfile) if logfile is not None else None
    if file_handler is not None:
        file_handler.name = NAME_FILE_HANDLER

    # create a map of handler names -> handlers
    new_handlers: Dict[str, logging.Handler] = {
        h.name: h  # type: ignore
        for h in [
            console_handler,
            file_handler,
        ]
        if h is not None
    }

    # get a map of existing handler names -> handlers
    old_handlers: Dict[str, logging.Handler] = {h.name: h for h in logging.root.handlers}  # type: ignore # noqa: E501

    # update the old handlers with the new handlers
    handlers = {base_console_handler.name: base_console_handler} | old_handlers | new_handlers

    logging.basicConfig(
        level=logging.NOTSET,  # root logger logs everything
        format=(DEBUG_FORMAT if loglevel == LogLevel.DEBUG else DEFAULT_FORMAT),
        datefmt="[%X]",
        handlers=handlers.values(),
        force=True,
    )

    handlers[NAME_CONSOLE_HANDLER].setLevel(
        loglevel.value if loglevel is not None else logging.WARNING
    )  # UI console log level set from --loglevel
    logging.info(f"Console log level: {logging.getLevelName(handlers[NAME_CONSOLE_HANDLER].level)}")

    if file_handler is not None:
        file_handler.setLevel(logging.DEBUG)  # file logs are always DEBUG
        file_handler.setFormatter(logging.Formatter(LOGFILE_FORMAT))
        logging.info(f"Log file {logfile} log level: {logging.getLevelName(file_handler.level)}")
