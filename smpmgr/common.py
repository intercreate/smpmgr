"""Common CLI helpers from rich, typer, click, etc."""

import asyncio
import logging
import sys
import threading
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, fields
from enum import Enum, unique
from pathlib import Path
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Final,
    Iterator,
    Type,
    TypedDict,
    TypeVar,
    assert_never,
)

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from serial import SerialException
from smp.exceptions import SMPBadStartDelimiter
from smpclient import SMPClient
from smpclient.generics import SMPRequest, TEr1, TEr2, TRep
from smpclient.transport.ble import SMPBLETransport
from smpclient.transport.bumble import (
    SMPBumbleTransport,
    SMPBumbleTransportDeviceNotFound,
    SMPBumbleTransportException,
    SMPBumbleTransportNotSMPServer,
)
from smpclient.transport.bumble.keystore import Custom, InMemory, KeystoreStrategy, Local, Tempfile
from smpclient.transport.bumble.pairing import DisplayOnly, KeyboardOnly, NoInputNoOutput
from smpclient.transport.serial import SMPSerialTransport
from smpclient.transport.udp import SMPUDPTransport

logger = logging.getLogger(__name__)


@unique
class PairOnConnectMode(Enum):
    KEYBOARD = 'keyboard'
    DISPLAY = 'display'
    NIO = 'nio'
    NONE = 'none'


DEFAULT_HCI: Final = "usb:0"
DEFAULT_KEYSTORE: Final = "local"
DEFAULT_PAIR_ON_CONNECT: Final = PairOnConnectMode.KEYBOARD

TSMPClient = TypeVar(
    "TSMPClient",
    bound=SMPClient,
)


@dataclass(frozen=True)
class TransportDefinition:
    port: str | None
    ble: str | None
    ip: str | None
    bumble: str | None


@dataclass(frozen=True)
class Options:
    timeout: float
    transport: TransportDefinition
    mtu: int | None
    baudrate: int | None
    line_length: int | None
    line_buffers: int | None
    hci: str
    keystore: str
    pair_on_connect: PairOnConnectMode
    pair_timeout_s: float


DEFAULT_LINE_LENGTH: Final = 128
DEFAULT_LINE_BUFFERS: Final = 2


# Stack of currently-active connect spinners.  Interactive callbacks deep
# inside `smpclient` (e.g. the bumble pair delegate's PIN prompt) consult this
# to suspend rich's Live display while reading from stdin — otherwise the
# spinner repaints over the prompt and the user never sees it.
_active_progress: Final[list[Progress]] = []


@contextmanager
def _registered_progress(progress: Progress) -> Iterator[Progress]:
    _active_progress.append(progress)
    try:
        yield progress
    finally:
        if _active_progress and _active_progress[-1] is progress:
            _active_progress.pop()


async def _async_input(prompt: str) -> str:
    """Async, cancellable stdin readline driven by a daemon thread.

    The daemon flag is load-bearing: when `pair_on_connect` times out, smpclient
    raises and our prompt coroutine is cancelled — but a non-daemon worker
    blocked in `input()` would otherwise block interpreter shutdown waiting for
    the user to press Enter, producing the `_enter_buffered_busy` abort we hit
    on hardware.  Daemon threads die with the process; the worst that survives
    is a benign shutdown warning if input was mid-read.
    """
    loop: Final = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    def _set_result(value: str) -> None:
        if not future.done():
            future.set_result(value)

    def _set_exception(exc: BaseException) -> None:
        if not future.done():
            future.set_exception(exc)

    def _read() -> None:
        try:
            sys.stdout.write(prompt)
            sys.stdout.flush()
            raw = input()
        except BaseException as exc:
            loop.call_soon_threadsafe(_set_exception, exc)
            return
        loop.call_soon_threadsafe(_set_result, raw)

    threading.Thread(target=_read, daemon=True, name="smpmgr-tty-input").start()
    return await future


async def _with_paused_spinner(coro_factory: Callable[[], Awaitable[str]]) -> str:
    """Run an async input coroutine with the topmost active spinner paused."""
    progress: Final = _active_progress[-1] if _active_progress else None
    if progress is not None:
        progress.stop()
    try:
        return await coro_factory()
    finally:
        if progress is not None:
            progress.start()


async def prompt_pin_tty() -> int | None:
    """Prompt for a 6-digit pairing PIN on the controlling terminal."""
    raw: Final = (
        await _with_paused_spinner(
            lambda: _async_input("Enter the 6-digit PIN shown on the device: ")
        )
    ).strip()
    if raw.isdigit() and len(raw) == 6:
        return int(raw)
    typer.echo(f"Invalid PIN {raw!r}; expected exactly 6 digits", err=True)
    return None


async def display_pin_tty(pin: int) -> None:
    """Show a peer-issued passkey to the user on the controlling terminal."""
    progress: Final = _active_progress[-1] if _active_progress else None
    if progress is not None:
        progress.stop()
    try:
        typer.echo(f"Enter this 6-digit PIN on the peer device: {pin:06d}")
    finally:
        if progress is not None:
            progress.start()


def build_pair_delegate(
    mode: PairOnConnectMode,
) -> KeyboardOnly | DisplayOnly | NoInputNoOutput | None:
    match mode:
        case PairOnConnectMode.NONE:
            return None
        case PairOnConnectMode.KEYBOARD:
            return KeyboardOnly(prompt_pin_tty)
        case PairOnConnectMode.DISPLAY:
            return DisplayOnly(display_pin_tty)
        case PairOnConnectMode.NIO:
            return NoInputNoOutput()
        case _ as unreachable:
            assert_never(unreachable)


def resolve_keystore_strategy(value: str) -> KeystoreStrategy:
    """Map a user-facing `--keystore` value to a smpclient keystore strategy.

    Bare names `local|tempfile|memory` select the corresponding standard
    strategy; anything else is treated as a custom filesystem path.
    """
    match value:
        case "local":
            return Local()
        case "tempfile":
            return Tempfile()
        case "memory":
            return InMemory()
        case _:
            return Custom(path=Path(value))


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
        match (options.line_length, options.line_buffers, options.mtu):
            case (int(), int(), None):
                kwargs['line_length'] = options.line_length
                kwargs['line_buffers'] = options.line_buffers
                kwargs['max_smp_encoded_frame_size'] = options.line_length * options.line_buffers
            case (int(), None, None):
                kwargs['line_length'] = options.line_length
                kwargs['line_buffers'] = DEFAULT_LINE_BUFFERS
                kwargs['max_smp_encoded_frame_size'] = options.line_length * DEFAULT_LINE_BUFFERS
            case (None, int(), None):
                kwargs['line_length'] = DEFAULT_LINE_LENGTH
                kwargs['line_buffers'] = options.line_buffers
                kwargs['max_smp_encoded_frame_size'] = DEFAULT_LINE_LENGTH * options.line_buffers
            case (None, None, int()):
                kwargs['line_length'] = options.mtu
                kwargs['line_buffers'] = 1
                kwargs['max_smp_encoded_frame_size'] = options.mtu
                typer.echo(
                    typer.style(
                        "Warning: --mtu is deprecated for serial transport."
                        " Use --line-length and --line-buffers instead."
                        f" --mtu {options.mtu} has been applied as"
                        f" --line-length {options.mtu} --line-buffers 1.",
                        fg=typer.colors.YELLOW,
                    )
                )
            case (None, None, None):
                kwargs['line_length'] = DEFAULT_LINE_LENGTH
                kwargs['line_buffers'] = DEFAULT_LINE_BUFFERS
                kwargs['max_smp_encoded_frame_size'] = DEFAULT_LINE_LENGTH * DEFAULT_LINE_BUFFERS
            case (_, _, int()):
                typer.echo("--mtu cannot be used with --line-length or --line-buffers.")
                raise typer.Exit(code=1)
            case _:
                assert_never((options.line_length, options.line_buffers, options.mtu))  # type: ignore[arg-type] # noqa: E501
        if options.baudrate is not None:
            kwargs['baudrate'] = options.baudrate
        return smp_client_cls(SMPSerialTransport(**kwargs), options.transport.port, options.timeout)
    elif options.transport.ble is not None:
        logger.info(f"Initializing SMPClient with the SMPBLETransport, {options.transport.ble=}")
        return smp_client_cls(
            SMPBLETransport(),
            options.transport.ble,
            options.timeout,
        )
    elif options.transport.bumble is not None:
        logger.info(
            f"Initializing SMPClient with the SMPBumbleTransport, {options.transport.bumble=}"
        )
        return smp_client_cls(
            SMPBumbleTransport(
                hci=options.hci,
                keystore=resolve_keystore_strategy(options.keystore),
                pair_on_connect=build_pair_delegate(options.pair_on_connect),
                pair_timeout_s=options.pair_timeout_s,
            ),
            options.transport.bumble,
            options.timeout,
        )
    elif options.transport.ip is not None:
        logger.info(f"Initializing SMPClient with the SMPUDPTransport, {options.transport.ip=}")
        if options.mtu is not None:
            return smp_client_cls(
                SMPUDPTransport(mtu=options.mtu), options.transport.ip, options.timeout
            )
        else:
            return smp_client_cls(SMPUDPTransport(), options.transport.ip, options.timeout)
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


async def _spinner_connect(smpclient: SMPClient) -> None:
    """Drive the connect-spinner UX; raises `typer.Exit` on failure."""
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress, _registered_progress(progress):
        connect_task_description = f"Connecting to {smpclient._address}..."
        connect_task = progress.add_task(description=connect_task_description, total=None)
        try:
            await smpclient.connect()
            progress.update(
                connect_task, description=f"{connect_task_description} OK", completed=True
            )
            return
        except asyncio.TimeoutError:
            logger.error("Transport error: connection timeout")
        except SerialException as e:
            logger.error(f"Serial transport error: {e.__class__.__name__} - {e}")
        except SMPBumbleTransportDeviceNotFound as e:
            logger.error(f"Bumble transport error: device not found - {e}")
        except SMPBumbleTransportNotSMPServer as e:
            logger.error(f"Bumble transport error: peer is not an SMP server - {e}")
        except SMPBumbleTransportException as e:
            logger.error(f"Bumble transport error: {e.__class__.__name__} - {e}")

        progress.update(
            connect_task, description=f"{connect_task_description} error", completed=True
        )
        raise typer.Exit(code=1)


@asynccontextmanager
async def connect_with_spinner(smpclient: SMPClient) -> AsyncIterator[SMPClient]:
    """Connect via spinner, yield the connected `SMPClient`, and disconnect on exit.

    Bumble's HCI USB transport owns background threads that post into the event
    loop; without an explicit `disconnect()` before `asyncio.run()` returns, the
    loop is torn down while libusb callbacks are still in flight, producing
    `RuntimeError: Event loop is closed` and hanging the process on exit.
    """
    await _spinner_connect(smpclient)
    try:
        yield smpclient
    finally:
        try:
            await smpclient.disconnect()
        except Exception as e:
            logger.warning(f"smpclient.disconnect() failed: {e.__class__.__name__} - {e}")


async def smp_request(
    smpclient: SMPClient,
    request: SMPRequest[TRep, TEr1, TEr2],
    description: str | None = None,
    timeout_s: float | None = None,
) -> TRep | TEr1 | TEr2:
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        description = description or f"Waiting for response to {request.__class__.__name__}..."
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
