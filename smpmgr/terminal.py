import asyncio
from typing import cast

import readchar
import typer
from serial import Serial

from smpmgr.common import Options


def terminal(ctx: typer.Context) -> None:
    """Open a terminal to the device."""

    options = cast(Options, ctx.obj)

    async def rx_from_device(port: Serial) -> None:
        while True:
            _bytes = port.read_all()
            if _bytes is not None:
                print(_bytes.decode(), end="", flush=True)
            await asyncio.sleep(0.020)

    def tx_keyboard_to_device(port: Serial) -> None:
        while True:
            char = readchar.readkey()
            if char == readchar.key.CTRL_C:
                raise KeyboardInterrupt
            elif char == readchar.key.UP:
                port.write(b"\x1b[A")
            elif char == readchar.key.DOWN:
                port.write(b"\x1b[B")
            else:
                port.write(char.encode())

    async def f() -> None:

        loop = asyncio.get_event_loop()

        with Serial(port=options.transport.port, baudrate=115200, timeout=options.timeout) as s:
            device_result, keyboard_result = await asyncio.gather(
                rx_from_device(s),
                loop.run_in_executor(None, tx_keyboard_to_device, s),
                return_exceptions=True,
            )

        print(device_result, keyboard_result)

    asyncio.run(f())
