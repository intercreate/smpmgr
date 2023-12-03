"""Constants for `smpmgr`."""
from typing import Final

import typer
from typing_extensions import Annotated

CONNECT_TIMEOUT_S: Final = 5.0

Address = Annotated[str, typer.Option(help="Serial port, e.g /dev/ttyACM0, COM1, etc.")]
