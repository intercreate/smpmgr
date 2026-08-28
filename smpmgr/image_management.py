"""The image subcommand group."""

import asyncio
import logging
from enum import StrEnum, unique
from io import BufferedReader
from pathlib import Path
from typing import Annotated, Final, TypeAlias, assert_never, cast

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
from smpclient.mcuboot import IMAGE_TLV, ImageInfo, ImageTLVValue, TLVNotFound
from smpclient.requests.image_management import ImageErase, ImageStatesRead, ImageStatesWrite

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request

logger = logging.getLogger(__name__)


@unique
class ImageFormat(StrEnum):
    MCUBOOT = "mcuboot"
    ANY = "any"


ImageFormatOption: TypeAlias = Annotated[
    ImageFormat,
    typer.Option(
        "--format",
        help="The expected image format for local inspection. "
        "'mcuboot' (default) inspects the image as an MCUboot image before upload. "
        "'any' skips local MCUboot inspection and does not attempt to interpret the file "
        "as an MCUboot image. "
        "This is useful when uploading images that are not in MCUboot format, such as "
        "custom bootloader formats (e.g., NXP's SB3.1). "
        "[bold red]WARNING[/bold red]: When using --format=any, the responsibility for "
        "validating image integrity is placed entirely on the device's bootloader. "
        "If the bootloader does not verify the image, corrupted firmware could be uploaded. "
        "[bold red]Only use --format=any if your bootloader performs its own image integrity "
        "validation.[/bold red]",
    ),
]


IMAGE_HASH_TLVS: Final = (IMAGE_TLV.SHA256, IMAGE_TLV.SHA384, IMAGE_TLV.SHA512)

IMAGE_HASH_TLV_NAMES: Final = "/".join(tlv.name for tlv in IMAGE_HASH_TLVS)


def _get_tlv_or_none(image_info: ImageInfo, tlv: IMAGE_TLV) -> ImageTLVValue | None:
    try:
        return image_info.get_tlv(tlv)
    except TLVNotFound:
        logger.info(f"{tlv.name} not found in image")
        return None


def get_image_hash_tlv(image_info: ImageInfo) -> ImageTLVValue | None:
    return next(filter(None, (_get_tlv_or_none(image_info, tlv) for tlv in IMAGE_HASH_TLVS)), None)


app = typer.Typer(name="image", help="The SMP Image Management Group.")


@app.command()
def state_read(ctx: typer.Context) -> None:
    """Request to read the state of FW images on the SMP Server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient)

        r = await smp_request(smpclient, ImageStatesRead(), "Waiting for image states...")

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


@app.command()
def state_write(
    ctx: typer.Context,
    hash: Annotated[
        str | None,
        typer.Argument(
            help="Hash of the image to mark for test on next reboot. "
            "MCUboot will temporarily swap to this image on the next reset. "
            "If the image boots successfully, use --confirm (or some other mechanism) to make it "
            "permanent (otherwise it will revert after another reset)."
        ),
    ] = None,
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Permanently confirm an image (prevent revert/rollback). "
            "Without HASH: confirms the currently running image (safe). "
            "With HASH: confirms a different image without testing (dangerous). "
            "[red]WARNING[/red]: Confirming an untested image can brick your device "
            "if it fails to boot. "
            "Best practice: always test first by marking for test swap, "
            "rebooting to verify the image works, "
            "then confirm the running image with 'smpmgr image state-write --confirm' "
            "(or some other mechanism).",
        ),
    ] = False,
) -> None:
    """Request to write the state of FW images on the SMP Server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)
    hash_bytes = bytes.fromhex(hash) if hash is not None else None

    async def f() -> None:
        await connect_with_spinner(smpclient)

        r = await smp_request(
            smpclient,
            ImageStatesWrite(hash=hash_bytes, confirm=confirm),
            "Waiting for image state write...",
        )

        if error(r):
            print(r)
        elif success(r):
            pass
        else:
            raise Exception("Unreachable")

    asyncio.run(f())


@app.command()
def erase(
    ctx: typer.Context,
    slot: Annotated[
        int,
        typer.Argument(help="Image slot to erase, as displayed by image state-read (0-indexed)"),
    ],
) -> None:
    """Request to erase an image slot on the SMP Server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient)

        r = await smp_request(smpclient, ImageErase(slot=slot), "Waiting for image erase...")

        if error(r):
            print(r)
        elif success(r):
            pass
        else:
            raise Exception("Unreachable")

    asyncio.run(f())


async def upload_with_progress_bar(
    smpclient: SMPClient, file: typer.FileBinaryRead | BufferedReader, slot: int = 0
) -> None:
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
        try:
            async for offset in smpclient.upload(image, slot):
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
    file: Annotated[Path, typer.Argument(help="Path to FW image")],
    slot: Annotated[int, typer.Option(help="The image slot to upload to")] = 0,
    format: ImageFormatOption = ImageFormat.MCUBOOT,
) -> None:
    """Upload a FW image."""

    match format:
        case ImageFormat.MCUBOOT:
            try:
                image_info = ImageInfo.load_file(str(file))
                logger.info(str(image_info))
            except Exception:
                logger.exception(
                    "Inspection of FW image failed. "
                    "If this is not an MCUboot image, retry with --format=any."
                )
                raise typer.Exit(code=1)
        case ImageFormat.ANY:
            pass
        case _ as unreachable:
            assert_never(unreachable)

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient)
        with open(file, "rb") as f:
            await upload_with_progress_bar(smpclient, f, slot)

    asyncio.run(f())
