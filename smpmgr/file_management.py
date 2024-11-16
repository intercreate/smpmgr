"""The image subcommand group."""

import asyncio
import logging
from io import BufferedReader
from pathlib import Path
from typing import cast

import typer
from rich import print
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from smp.exceptions import SMPBadStartDelimiter
from smpclient import SMPClient
from smpclient.generics import error, success
from smpclient.requests.file_management import (
    FileHashChecksum,
    FileStatus,
    SupportedFileHashChecksumTypes,
)
from typing_extensions import Annotated

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request

app = typer.Typer(name="file", help="The SMP File Management Group.")
logger = logging.getLogger(__name__)


@app.command()
def get_supported_hash_types(ctx: typer.Context) -> None:
    """Request the supported hash types."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smp_request(smpclient, options, SupportedFileHashChecksumTypes(), "Waiting for supported hash types...")  # type: ignore # noqa

        if error(r):
            print(r)
        elif success(r):
            print(r.types)
        else:
            raise Exception("Unreachable")

    asyncio.run(f())


@app.command()
def get_hash(
    ctx: typer.Context, file: Annotated[str, typer.Argument(help="Path to file on the SMP Server")]
) -> None:
    """Request the hash of a file on the SMP Server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smp_request(smpclient, options, FileHashChecksum(name=file), "Waiting for hash...")  # type: ignore # noqa

        if error(r) or success(r):
            print(r)
        else:
            raise Exception("Unreachable")

    asyncio.run(f())


@app.command()
def read_size(
    ctx: typer.Context, file: Annotated[str, typer.Argument(help="Path to file on the SMP Server")]
) -> None:
    """Request to read the size of a file on the SMP Server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smp_request(smpclient, options, FileStatus(name=file), "Waiting for file size...")  # type: ignore # noqa

        if error(r):
            print(r)
        elif success(r):
            print(r.len)
        else:
            raise Exception("Unreachable")

    asyncio.run(f())


async def upload_with_progress_bar(
    smpclient: SMPClient, file: typer.FileBinaryRead | BufferedReader, destination: str
) -> None:
    """Animate a progress bar while uploading the file."""

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
        file_data = file.read()
        file.close()
        task = progress.add_task("Uploading", total=len(file_data), filename=file.name, start=True)
        try:
            async for offset in smpclient.upload_file(file_data, destination):
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
    file: Annotated[Path, typer.Argument(help="Path to file")],
    destination: Annotated[str, typer.Argument(help="The destination on the SMP Server")],
) -> None:
    """Upload a file."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        with open(file, "rb") as f:
            await upload_with_progress_bar(smpclient, f, destination)

    asyncio.run(f())


@app.command()
def download(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="The file on the SMP Server")],
    destination: Annotated[Path, typer.Argument(help="The destination on the local filesystem")],
) -> None:
    """Download a file."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        with destination.open("wb") as dest_f:
            file_data = await smpclient.download_file(file)
            dest_f.write(file_data)

    asyncio.run(f())
