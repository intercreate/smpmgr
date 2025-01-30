"""Entry point for the `smpmgr` application."""

import asyncio
import logging
from importlib.metadata import version as get_version
from pathlib import Path
from typing import Final, cast

import typer
from rich import print
from smp import error as smperr
from smp.os_management import OS_MGMT_RET_RC
from smpclient.generics import error, error_v1, error_v2, success
from smpclient.mcuboot import IMAGE_TLV, ImageInfo, TLVNotFound
from smpclient.requests.image_management import ImageStatesWrite
from smpclient.requests.os_management import ResetWrite
from typing_extensions import Annotated, assert_never

from smpmgr import file_management, image_management, os_management, terminal
from smpmgr.common import (
    Options,
    TransportDefinition,
    connect_with_spinner,
    get_smpclient,
    smp_request,
)
from smpmgr.image_management import upload_with_progress_bar
from smpmgr.logging import LogLevel, setup_logging
from smpmgr.user import intercreate

logger = logging.getLogger(__name__)

HELP_LINES: Final = (
    f"Simple Management Protocol (SMP) Manager Version {get_version('smpmgr')}\n",
    "Copyright (c) 2023-2024 Intercreate, Inc. and Contributors\n",
)

app: Final = typer.Typer(help="\n".join(HELP_LINES))
app.add_typer(os_management.app)
app.add_typer(image_management.app)
app.add_typer(file_management.app)
app.add_typer(intercreate.app)
app.command()(terminal.terminal)


@app.callback(invoke_without_command=True)
def options(
    ctx: typer.Context,
    port: str = typer.Option(
        None, help="The serial port to connect to, e.g. COM1, /dev/ttyACM0, etc."
    ),
    ble: str = typer.Option(None, help="The Bluetooth address to connect to"),
    timeout: float = typer.Option(
        2.0, help="Transport timeout in seconds; how long to wait for requests"
    ),
    mtu: int = typer.Option(
        4096,
        help=(
            "Maximum transmission unit supported by the SMP server serial transport."
            "  Ignored for BLE transport since the BLE connection will report MTU."
        ),
    ),
    loglevel: LogLevel = typer.Option(None, help="Debug log level"),
    logfile: Path = typer.Option(None, help="Log file path"),
    version: Annotated[bool, typer.Option("--version", help="Show the version and exit.")] = False,
) -> None:
    if version:
        print(get_version('smpmgr'))
        raise typer.Exit()

    setup_logging(loglevel, logfile)

    ctx.obj = Options(timeout=timeout, transport=TransportDefinition(port=port, ble=ble), mtu=mtu)
    logger.info(ctx.obj)

    if ctx.invoked_subcommand is None:
        if loglevel is not None or logfile is not None:
            raise typer.Exit()
        print("A command is required, see [bold]--help[/bold] for available commands.")
        raise typer.Exit()

    # TODO: type of transport is inferred from the argument given (--port, --ble, --usb, etc), but
    # it must be the case that only one is provided.


@app.command()
def upgrade(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="Path to FW image")],
    slot: Annotated[int, typer.Option(help="The image slot to upload to")] = 0,
) -> None:
    """Upload a FW image, mark it for next boot, and reset the device."""

    try:
        image_info = ImageInfo.load_file(str(file))
        logger.info(str(image_info))
    except Exception as e:
        typer.echo(f"Inspection of FW image failed: {e}")
        raise typer.Exit(code=1)

    try:
        image_tlv_sha256 = image_info.get_tlv(IMAGE_TLV.SHA256)
        logger.info(f"IMAGE_TLV_SHA256: {image_tlv_sha256}")
    except TLVNotFound:
        typer.echo("Could not find IMAGE_TLV_SHA256 in image.")
        raise typer.Exit(code=1)

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        with open(file, "rb") as f:
            await upload_with_progress_bar(smpclient, f, slot)

        if slot != 0:
            # mark the new image for testing (swap)
            image_states_response = await smp_request(
                smpclient,
                options,
                ImageStatesWrite(hash=image_tlv_sha256.value),
                "Marking uploaded image for test upgrade...",
            )
            if success(image_states_response):
                pass
            elif error(image_states_response):
                print(image_states_response)
                raise typer.Exit(code=1)
            else:
                assert_never(image_states_response)

        reset_response = await smp_request(smpclient, options, ResetWrite())
        if success(reset_response):
            pass
        elif error(reset_response):
            if error_v1(reset_response):
                if reset_response.rc != smperr.MGMT_ERR.EOK:
                    print(reset_response)
                    raise typer.Exit(code=1)
            elif error_v2(reset_response):
                if reset_response.err.rc != OS_MGMT_RET_RC.OK:
                    print(reset_response)
                    raise typer.Exit(code=1)
            else:
                assert_never(reset_response)
        else:
            assert_never(reset_response)

        print("Upgrade complete.")

        if slot != 0:
            print("The device may take a few minutes to complete FW swap.")

    asyncio.run(f())


@app.command()
def shell() -> None:
    """Open the `smpmgr` interactive shell. Type 'exit' or 'quit' to exit."""

    print("".join(HELP_LINES))
    print("Type 'exit' or 'quit' to exit the shell.\n")

    while True:
        args = typer.prompt("smpmgr", prompt_suffix=' >').split()

        if args[0] in {"exit", "quit"}:
            break
        if args[0] == "shell":
            print("The 'shell' command cannot be used from within the shell.")
            continue

        try:
            app(args)
        except SystemExit:
            continue
