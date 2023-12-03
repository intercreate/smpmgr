"""Entry point for the `smpmgr` application."""

import asyncio

import typer
from rich import print
from smp.os_management import OS_MGMT_RET_RC
from smpclient import SMPClient
from smpclient.generics import error, success
from smpclient.requests.os_management import ResetWrite
from smpclient.transport.serial import SMPSerialTransport
from typing_extensions import Annotated

from smpmgr import const, image_management, os_management
from smpmgr.common import connect_with_spinner
from smpmgr.image_management import upload_with_progress_bar

app = typer.Typer()
app.add_typer(os_management.app)
app.add_typer(image_management.app)


@app.command()
def upgrade(
    address: const.Address,
    file: Annotated[typer.FileBinaryRead, typer.Argument(help="Path to FW image")],
) -> None:
    """Upload a FW image, mark it for next boot, and reset the device."""
    smpclient = SMPClient(SMPSerialTransport(), address)

    async def f() -> None:
        if await connect_with_spinner(smpclient) is False:
            print("Timeout")
            return

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
