import asyncio
from typing import cast

import typer
from rich import print
from smpclient.requests.statistics_management import ListOfGroups, GroupData

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request

app = typer.Typer(name="stat", help="The SMP stat Management Group.")


@app.command(name="list")
def list_stats(ctx: typer.Context) -> None:
    """Request that the SMP Server list all available statistics groups."""
    
    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, ListOfGroups())  # type: ignore
        print(r)

    asyncio.run(f())


@app.command(name="smp_svr_stats")
def smp_svr_stats(ctx: typer.Context) -> None:
    """Request statistics related to the SMP server itself."""
    
    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, GroupData(name="smp_svr_stats"))
        print(r)

    asyncio.run(f())