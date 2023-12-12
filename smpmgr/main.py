"""Entry point for the `smpmgr` application."""

import asyncio
from typing import cast

import typer
from rich import print
from smp.os_management import OS_MGMT_RET_RC
from smpclient.generics import error, success
from smpclient.requests.os_management import ResetWrite
from typing_extensions import Annotated

from smpmgr import image_management, os_management
from smpmgr.common import Options, TransportDefinition, connect_with_spinner, get_smpclient
from smpmgr.image_management import upload_with_progress_bar

app = typer.Typer()
app.add_typer(os_management.app)
app.add_typer(image_management.app)


@app.callback()
def options(
    ctx: typer.Context,
    port: str = typer.Option(
        None, help="The serial port to connect to, e.g. COM1, /dev/ttyACM0, etc."
    ),
    timeout: float = typer.Option(
        2.0, help="Transport timeout in seconds; how long to wait for requests"
    ),
) -> None:
    ctx.obj = Options(timeout=timeout, transport=TransportDefinition(port=port))

    # TODO: type of transport is inferred from the argument given (--port, --ble, --usb, etc), but
    # it must be the case that only one is provided.


@app.command()
def upgrade(
    ctx: typer.Context,
    file: Annotated[typer.FileBinaryRead, typer.Argument(help="Path to FW image")],
) -> None:
    """Upload a FW image, mark it for next boot, and reset the device."""

    smpclient = get_smpclient(cast(Options, ctx.obj))

    async def f() -> None:
        await connect_with_spinner(smpclient)
        await upload_with_progress_bar(smpclient, file)

        r = await smpclient.request(ResetWrite())  # type: ignore
        if error(r):
            if r.rc != OS_MGMT_RET_RC.OK:
                print(r)
                return
        elif success(r):
            pass
        else:
            raise Exception("Unreachable")

        print("Upgrade complete.  The device may take a few minutes to complete FW swap.")

    asyncio.run(f())
