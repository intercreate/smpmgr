import asyncio
import logging
from enum import IntEnum, unique
from typing import cast

import smp.error as smperr
import smp.message as smpmsg
import typer
from rich import print

from smpmgr.common import Options, connect_with_spinner, get_smpclient

app = typer.Typer(name="another", help="Another user group 89")
logger = logging.getLogger(__name__)


@unique
class ANOTHER_RET_RC(IntEnum):
    OK = 0
    NOT_OK = 1


class AnotherErrorV1(smperr.ErrorV1):
    _GROUP_ID = 89


class AnotherErrorV2(smperr.ErrorV2[ANOTHER_RET_RC]):
    _GROUP_ID = 89


class AnotherWriteRequest(smpmsg.WriteRequest):
    _GROUP_ID = 89
    _COMMAND_ID = 0

    d: str


class AnotherWriteResponse(smpmsg.WriteResponse):
    _GROUP_ID = 89
    _COMMAND_ID = 0

    r: str


class AnotherWrite(AnotherWriteRequest):
    _Response = AnotherWriteResponse
    _ErrorV1 = AnotherErrorV1
    _ErrorV2 = AnotherErrorV2


class AnotherReadRequest(smpmsg.ReadRequest):
    _GROUP_ID = 89
    _COMMAND_ID = 1


class AnotherReadResponse(smpmsg.ReadResponse):
    _GROUP_ID = 89
    _COMMAND_ID = 1

    something: int


class AnotherRead(AnotherReadRequest):
    _Response = AnotherReadResponse
    _ErrorV1 = AnotherErrorV1
    _ErrorV2 = AnotherErrorV2


@app.command()
def write(ctx: typer.Context, message: str) -> None:
    """Another echo write."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smpclient.request(AnotherWrite(d=message))
        print(r)

    asyncio.run(f())


@app.command()
def read(ctx: typer.Context) -> None:
    """Another echo read."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        r = await smpclient.request(AnotherRead())
        print(r)

    asyncio.run(f())
