"""Common CLI helpers from rich, typer, click, etc."""
import asyncio

from rich.progress import Progress, SpinnerColumn, TextColumn
from smpclient import SMPClient

from smpmgr import const


async def connect_with_spinner(smpclient: SMPClient) -> bool:
    """Animate a spinner while waiting to connect to the SMP Server."""
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True
    ) as progress:
        progress_connect = progress.add_task(
            description=f"Connecting to {smpclient._address}...", total=None
        )
        try:
            await asyncio.wait_for(smpclient.connect(), timeout=const.CONNECT_TIMEOUT_S)
            progress.remove_task(progress_connect)
            return True
        except asyncio.TimeoutError:
            return False
