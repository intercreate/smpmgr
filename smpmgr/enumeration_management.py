"""The enum subcommand group."""

import asyncio
import logging
from typing import List, cast

import typer
from rich import print
from smpclient.requests.enumeration_management import GroupDetails, ListSupportedGroups
from typing_extensions import Annotated

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request

app = typer.Typer(name="enum", help="The SMP Enumeration Management Group.")
logger = logging.getLogger(__name__)


@app.command()
def get_supported_groups(ctx: typer.Context) -> None:
    """Request groups supported by the server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, ListSupportedGroups(), "Waiting for supported groups...")  # type: ignore # noqa
        print(r)

    asyncio.run(f())


@app.command()
def get_group_details(
    ctx: typer.Context,
    groups: Annotated[List[int], typer.Argument(help="Groups to retrieve details for")],
) -> None:
    """Request groups supported by the server."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, GroupDetails(groups=groups), "Waiting for group details...")  # type: ignore # noqa
        print(r)

    asyncio.run(f())
