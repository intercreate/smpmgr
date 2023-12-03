import asyncio

import typer
from rich import print
from smpclient import SMPClient
from smpclient.requests.os_management import EchoWrite, ResetWrite
from smpclient.transport.serial import SMPSerialTransport

from smpmgr import const

app = typer.Typer(name="os", help="The SMP OS Management Group.")


@app.command()
def echo(address: str, message: str) -> None:
    """Request that the SMP Server echo the given message."""
    s = SMPClient(SMPSerialTransport(), address)

    async def f() -> None:
        await s.connect()
        r = await s.request(EchoWrite(d=message))  # type: ignore
        print(r)

    asyncio.run(f())


@app.command()
def reset(address: const.Address) -> None:
    """Request that the SMP Server reset the device."""
    s = SMPClient(SMPSerialTransport(), address)

    async def f() -> None:
        await s.connect()
        r = await s.request(ResetWrite())  # type: ignore
        print(r)

    asyncio.run(f())
