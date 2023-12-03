"""The image subcommand group."""

import asyncio

import typer
from rich import print
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from smpclient import SMPClient
from smpclient.generics import error, success
from smpclient.requests.image_management import ImageStatesRead
from smpclient.transport.serial import SMPSerialTransport
from typing_extensions import Annotated

from smpmgr import const
from smpmgr.common import connect_with_spinner

app = typer.Typer(name="image", help="The SMP Image Management Group.")


@app.command()
def state_read(address: const.Address) -> None:
    """Request to read the state of FW images on the SMP Server."""

    smpclient = SMPClient(SMPSerialTransport(), address)

    async def f() -> None:
        if await connect_with_spinner(smpclient) is False:
            print("Timeout")
            return

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
        ) as progress:
            progress.add_task(description="Requested image states...", total=None)

            try:
                r = await asyncio.wait_for(
                    smpclient.request(ImageStatesRead()), timeout=const.CONNECT_TIMEOUT_S  # type: ignore # noqa
                )
            except asyncio.TimeoutError:
                print("Timeout")
                return

        if error(r):
            print(r)
        elif success(r):
            if len(r.images) == 0:
                print("No images on device!")
            for image in r.images:
                print(image)
            if r.splitStatus is not None:
                print(f"splitStatus: {r.splitStatus}")
        else:
            raise Exception("Unreachable")

    asyncio.run(f())


async def upload_with_progress_bar(smpclient: SMPClient, file: typer.FileBinaryRead) -> None:
    """Animate a progress bar while uploading the FW image."""

    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
    ) as progress:
        image = file.read()
        file.close()
        task = progress.add_task("Uploading", total=len(image), filename=file.name, start=True)
        async for offset in smpclient.upload(image):
            progress.update(task, completed=offset)


@app.command()
def upload(
    address: const.Address,
    file: Annotated[typer.FileBinaryRead, typer.Argument(help="Path to FW image")],
) -> None:
    """Upload a FW image."""
    smpclient = SMPClient(SMPSerialTransport(), address)

    async def f() -> None:
        if await connect_with_spinner(smpclient) is False:
            print("Timeout")
            return

        await upload_with_progress_bar(smpclient, file)

    asyncio.run(f())
