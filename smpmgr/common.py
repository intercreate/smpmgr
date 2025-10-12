"""Common CLI helpers from rich, typer, click, etc."""

import asyncio
import logging
from dataclasses import dataclass, fields
from typing import Type, TypedDict, TypeVar

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from serial import SerialException
from smp.exceptions import SMPBadStartDelimiter
from smpclient import SMPClient
from smpclient.generics import SMPRequest, TEr1, TEr2, TRep
from smpclient.transport.ble import SMPBLETransport
from smpclient.transport.serial import SMPSerialTransport
from smpclient.transport.udp import SMPUDPTransport

logger = logging.getLogger(__name__)

TSMPClient = TypeVar(
    "TSMPClient",
    bound=SMPClient,
)


@dataclass(frozen=True)
class TransportDefinition:
    port: str | None
    ble: str | None
    ip: str | None


@dataclass(frozen=True)
class Options:
    timeout: float
    transport: TransportDefinition
    mtu: int | None
    baudrate: int | None


class SMPSerialTransportKwargs(TypedDict, total=False):
    max_smp_encoded_frame_size: int
    line_length: int
    line_buffers: int
    baudrate: int


def get_custom_smpclient(options: Options, smp_client_cls: Type[TSMPClient]) -> TSMPClient:
    """Return an `SMPClient` subclass to the chosen transport or raise `typer.Exit`."""
    if options.transport.port is not None:
        logger.info(
            f"Initializing SMPClient with the SMPSerialTransport, {options.transport.port=}"
        )
        kwargs: SMPSerialTransportKwargs = {}
        if options.mtu is not None:
            kwargs['max_smp_encoded_frame_size'] = options.mtu
            kwargs['line_length'] = options.mtu
            kwargs['line_buffers'] = 1
        if options.baudrate is not None:
            kwargs['baudrate'] = options.baudrate
        return smp_client_cls(SMPSerialTransport(**kwargs), options.transport.port)
    elif options.transport.ble is not None:
        logger.info(f"Initializing SMPClient with the SMPBLETransport, {options.transport.ble=}")
        return smp_client_cls(
            SMPBLETransport(),
            options.transport.ble,
        )
    elif options.transport.ip is not None:
        logger.info(f"Initializing SMPClient with the SMPUDPTransport, {options.transport.ip=}")
        if options.mtu is not None:
            return smp_client_cls(SMPUDPTransport(mtu=options.mtu), options.transport.ip)
        else:
            return smp_client_cls(SMPUDPTransport(), options.transport.ip)
    else:
        typer.echo(
            f"A transport option is required; "
            f"one of [{', '.join(map(lambda x: '--' + x.name, fields(options.transport)))}]."
        )
        typer.echo("See smpmgr --help.")
        raise typer.Exit(code=1)


def get_smpclient(options: Options) -> SMPClient:
    """Return an `SMPClient` to the chosen transport or raise `typer.Exit`."""
    return get_custom_smpclient(options, SMPClient)


async def connect_with_spinner(smpclient: SMPClient, timeout_s: float) -> None:
    """Spin while connecting to the SMP Server; raises `typer.Exit` if connection fails."""
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        connect_task_description = f"Connecting to {smpclient._address}..."
        connect_task = progress.add_task(description=connect_task_description, total=None)
        try:
            await smpclient.connect(timeout_s)
            progress.update(
                connect_task, description=f"{connect_task_description} OK", completed=True
            )
            return
        except asyncio.TimeoutError:
            logger.error("Transport error: connection timeout")
        except SerialException as e:
            logger.error(f"Serial transport error: {e.__class__.__name__} - {e}")

        progress.update(
            connect_task, description=f"{connect_task_description} error", completed=True
        )
        raise typer.Exit(code=1)


async def smp_request(
    smpclient: SMPClient,
    options: Options,
    request: SMPRequest[TRep, TEr1, TEr2],
    description: str | None = None,
    timeout_s: float | None = None,
) -> TRep | TEr1 | TEr2:
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        description = description or f"Waiting for response to {request.__class__.__name__}..."
        timeout_s = timeout_s if timeout_s is not None else options.timeout
        task = progress.add_task(description=description, total=None)
        try:
            r = await smpclient.request(request, timeout_s)
            progress.update(task, description=f"{description} OK", completed=True)
            return r
        except asyncio.TimeoutError:
            progress.update(task, description=f"{description} timeout", completed=True)
            logger.error("Timeout waiting for response")
            raise typer.Exit(code=1)
        except SMPBadStartDelimiter:
            progress.update(task, description=f"{description} SMP error", completed=True)
            logger.error("Is the device an SMP server?")
            raise typer.Exit(code=1)
        except OSError as e:
            progress.update(task, description=f"{description} OS error", completed=True)
            logger.error(f"Connection to device lost: {e.__class__.__name__} - {e}")
            raise typer.Exit(code=1)
