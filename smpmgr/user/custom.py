import asyncio
import logging
from enum import IntEnum, unique
from typing import cast

import smp.error as smperr
import smp.message as smpmsg
import typer
from rich import print

from smpmgr.common import Options, connect_with_spinner, get_smpclient

app = typer.Typer(name="custom", help="Custom user group 88")
logger = logging.getLogger(__name__)


@unique
class CUSTOM_RET_RC(IntEnum):
    OK = 0
    NOT_OK = 1


class CustomErrorV1(smperr.ErrorV1):
    _GROUP_ID = 88


class CustomErrorV2(smperr.ErrorV2[CUSTOM_RET_RC]):
    _GROUP_ID = 88


class CustomWriteRequest(smpmsg.WriteRequest):
    _GROUP_ID = 88
    _COMMAND_ID = 0

    d: str


class CustomWriteResponse(smpmsg.WriteResponse):
    _GROUP_ID = 88
    _COMMAND_ID = 0

    r: str


class CustomWrite(CustomWriteRequest):
    _Response = CustomWriteResponse
    _ErrorV1 = CustomErrorV1
    _ErrorV2 = CustomErrorV2


class CustomReadRequest(smpmsg.ReadRequest):
    _GROUP_ID = 88
    _COMMAND_ID = 1


class CustomReadResponse(smpmsg.ReadResponse):
    _GROUP_ID = 88
    _COMMAND_ID = 1

    something: int


class CustomRead(CustomReadRequest):
    _Response = CustomReadResponse
    _ErrorV1 = CustomErrorV1
    _ErrorV2 = CustomErrorV2


@app.command()
def write(ctx: typer.Context, message: str) -> None:
    """Custom echo write."""

    smpclient = get_smpclient(cast(Options, ctx.obj))

    async def f() -> None:
        await connect_with_spinner(smpclient)

        r = await smpclient.request(CustomWrite(d=message))
        print(r)

    asyncio.run(f())


@app.command()
def read(ctx: typer.Context) -> None:
    """Custom echo read."""

    smpclient = get_smpclient(cast(Options, ctx.obj))

    async def f() -> None:
        await connect_with_spinner(smpclient)

        r = await smpclient.request(CustomRead())
        print(r)

    asyncio.run(f())
