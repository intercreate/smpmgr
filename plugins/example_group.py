import asyncio
import logging
from enum import IntEnum, unique
from typing import cast

import smp.error as smperr
import smp.message as smpmsg
import typer
from rich import print

from smpmgr.common import Options, connect_with_spinner, get_smpclient

app = typer.Typer(name="example", help="Example user group 88")
logger = logging.getLogger(__name__)


@unique
class EXAMPLE_RET_RC(IntEnum):
    OK = 0
    NOT_OK = 1


class ExampleErrorV1(smperr.ErrorV1):
    _GROUP_ID = 88


class ExampleErrorV2(smperr.ErrorV2[EXAMPLE_RET_RC]):
    _GROUP_ID = 88


class ExampleWriteRequest(smpmsg.WriteRequest):
    _GROUP_ID = 88
    _COMMAND_ID = 0

    d: str


class ExampleWriteResponse(smpmsg.WriteResponse):
    _GROUP_ID = 88
    _COMMAND_ID = 0

    r: str


class ExampleWrite(ExampleWriteRequest):
    _Response = ExampleWriteResponse
    _ErrorV1 = ExampleErrorV1
    _ErrorV2 = ExampleErrorV2


class ExampleReadRequest(smpmsg.ReadRequest):
    _GROUP_ID = 88
    _COMMAND_ID = 1


class ExampleReadResponse(smpmsg.ReadResponse):
    _GROUP_ID = 88
    _COMMAND_ID = 1

    something: int


class ExampleRead(ExampleReadRequest):
    _Response = ExampleReadResponse
    _ErrorV1 = ExampleErrorV1
    _ErrorV2 = ExampleErrorV2


@app.command()
def write(ctx: typer.Context, message: str) -> None:
    """Example echo write."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smpclient.request(ExampleWrite(d=message))
        print(r)

    asyncio.run(f())


@app.command()
def read(ctx: typer.Context) -> None:
    """Example echo read."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smpclient.request(ExampleRead())
        print(r)

    asyncio.run(f())
