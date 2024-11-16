import asyncio
from typing import cast

import typer
from rich import print
from smpclient.requests.os_management import EchoWrite, ResetWrite

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request

app = typer.Typer(name="os", help="The SMP OS Management Group.")


@app.command()
def echo(ctx: typer.Context, message: str) -> None:
    """Request that the SMP Server echo the given message."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, EchoWrite(d=message))  # type: ignore
        print(r)

    asyncio.run(f())


@app.command()
def reset(ctx: typer.Context) -> None:
    """Request that the SMP Server reset the device."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, ResetWrite())  # type: ignore
        print(r)

    asyncio.run(f())
