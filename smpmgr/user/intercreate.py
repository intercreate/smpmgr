"""The Intercreate (ic) subcommand group."""

import asyncio
import logging
from io import BufferedReader
from pathlib import Path
from typing import cast

import typer
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from smp import header as smphdr
from smp.exceptions import SMPBadStartDelimiter
from smpclient.extensions import intercreate as ic
from typing_extensions import Annotated

from smpmgr.common import Options, connect_with_spinner, get_custom_smpclient

app = typer.Typer(
    name="ic", help=f"The Intercreate User Group ({smphdr.UserGroupId.INTERCREATE.value})"
)
logger = logging.getLogger(__name__)


async def upload_with_progress_bar(
    smpclient: ic.ICUploadClient, file: typer.FileBinaryRead | BufferedReader, image: int = 0
) -> None:
    """Animate a progress bar while uploading the data."""

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
        data = file.read()
        file.close()
        task = progress.add_task("Uploading", total=len(data), filename=file.name, start=True)
        try:
            async for offset in smpclient.ic_upload(data, image):
                progress.update(task, completed=offset)
                logger.info(f"Upload {offset=}")
        except SMPBadStartDelimiter as e:
            progress.stop()
            logger.info(f"Bad start delimiter: {e}")
            logger.error("Got an unexpected response, is the device an SMP server?")
            raise typer.Exit(code=1)
        except OSError as e:
            logger.error(f"Connection to device lost: {e.__class__.__name__} - {e}")
            raise typer.Exit(code=1)


@app.command()
def upload(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="Path to binary data")],
    image: Annotated[int, typer.Option(help="The image slot to upload to")] = 0,
) -> None:
    """Upload data to custom image slots, like a secondary MCU or external storage."""

    options = cast(Options, ctx.obj)
    smpclient = get_custom_smpclient(options, ic.ICUploadClient)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        with open(file, "rb") as f:
            await upload_with_progress_bar(smpclient, f, image)

    asyncio.run(f())
