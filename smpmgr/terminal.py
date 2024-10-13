import asyncio
import logging
from typing import Final, cast

import readchar
import typer
from serial import Serial, SerialException
from serial.tools.list_ports import grep

from smpmgr.common import Options

logger = logging.getLogger(__name__)

MAP_KEY_TO_BYTES: Final = {
    readchar.key.CTRL_C: b"\x03",
    readchar.key.UP: b"\x1b[A",
    readchar.key.DOWN: b"\x1b[B",
    readchar.key.LEFT: b"\x1b[D",
    readchar.key.RIGHT: b"\x1b[C",
    readchar.key.ESC: b"\x1b",
}


def terminal(ctx: typer.Context) -> None:
    """Open a terminal to the device."""

    options = cast(Options, ctx.obj)

    if options.transport.port is None:
        print("--port <port> option is required for the terminal, e.g.")
        print("smpmgr --port COM1 terminal")
        return

    async def f() -> None:
        while True:
            print(f"\n\x1b[2mWaiting for {options.transport.port}", end="", flush=True)

            MAX_DOTS = 3
            dot_count = 0
            while len(tuple(grep(rf"{options.transport.port}"))) == 0:
                print(
                    f"\rWaiting for {options.transport.port}"
                    + "." * dot_count
                    + " " * (MAX_DOTS - dot_count),
                    end="",
                    flush=True,
                )
                dot_count = (dot_count + 1) % (MAX_DOTS + 1)
                await asyncio.sleep(0.250)

            print(f"\nOpening terminal to {options.transport.port}...", end="")

            with Serial(port=options.transport.port, baudrate=115200, timeout=options.timeout) as s:
                print("OK")
                print("Press Ctrl-T to exit the terminal.\x1b[22m")
                print()
                device_result, keyboard_result = await asyncio.wait(
                    (
                        asyncio.create_task(_rx_from_device(s)),
                        asyncio.create_task(asyncio.to_thread(_tx_keyboard_to_device, s)),
                    ),
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                logger.debug(f"{device_result=}, {keyboard_result=}")

    asyncio.run(f())


async def _rx_from_device(port: Serial) -> None:
    """Async poll of the serial port for incoming data.

    Can be replaced when pyserial is replaced."""

    while True:
        _bytes = port.read_all()
        if _bytes is not None:
            print(_bytes.decode(), end="", flush=True)
        await asyncio.sleep(0.020)


def _tx_keyboard_to_device(port: Serial) -> None:
    """Blocking read of keyboard input."""
    while True:
        try:
            key = readchar.readkey()
        except KeyboardInterrupt:
            key = readchar.key.CTRL_C
        if key == readchar.key.CTRL_T:
            raise KeyboardInterrupt
        try:
            port.write(MAP_KEY_TO_BYTES[key])
        except KeyError:
            port.write(key.encode())
