"""Logging configuration for smpmgr."""

import asyncio
import logging
from enum import Enum, unique
from pathlib import Path

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


def setup_logging(loglevel: LogLevel, logfile: Path | None) -> None:
    """Setup logging for smpmgr."""

    DEBUG_FORMAT = "%(message)s - %(pathname)s:%(lineno)s"
    DEFAULT_FORMAT = "%(message)s - %(module)s:%(lineno)s"
    LOGFILE_FORMAT = "%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)s - %(message)s"

    console_handler = RichHandler(
        rich_tracebacks=True, tracebacks_suppress=[click, typer, asyncio, serial]
    )
    file_handler = logging.FileHandler(logfile) if logfile is not None else None

    logging.basicConfig(
        level=logging.NOTSET,  # root logger logs everything
        format=(DEBUG_FORMAT if loglevel == LogLevel.DEBUG else DEFAULT_FORMAT),
        datefmt="[%X]",
        handlers=((console_handler,) + ((file_handler,) if file_handler is not None else ())),
    )

    console_handler.setLevel(loglevel.value)  # UI console log level set from --loglevel
    logging.info(f"Console log level: {logging.getLevelName(console_handler.level)}")

    logging.info(f"Log file: {logfile}")
    if file_handler is not None:
        file_handler.setLevel(logging.DEBUG)  # file logs are always DEBUG
        file_handler.setFormatter(logging.Formatter(LOGFILE_FORMAT))
        logging.info(f"Log file {logfile} log level: {logging.getLevelName(file_handler.level)}")
