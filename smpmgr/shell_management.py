import asyncio
import shlex
from typing import Annotated as A
from typing import Final, cast

import typer
from rich import print as rich_print
from smpclient.generics import error, success
from smpclient.requests.shell_management import Execute
from typing_extensions import assert_never

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request


def shell(
    ctx: typer.Context,
    command: str = typer.Argument(
        help="Command string to run, e.g. \"gpio conf gpio@49000000 0 i\""
    ),
    timeout: float = typer.Option(2.0, help="Timeout in seconds for the command to complete"),
    verbose: A[
        bool, typer.Option("--verbose", help="Print the raw success response")  # noqa: F821,F722
    ] = False,
) -> None:
    """Send a shell command to the device."""

    options: Final = cast(Options, ctx.obj)
    smpclient: Final = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        response: Final = await smp_request(
            smpclient,
            options,
            Execute(argv=shlex.split(command)),
            f"Waiting response to {command}...",
            timeout_s=timeout,
        )
        if success(response):
            if response.ret == 0:  # success, regular text color
                print(response.o)
            elif response.ret > 0:
                rich_print(f"[yellow]Return code: {response.ret}[/yellow]")
                print(response.o)
            else:  # non-zero return code, error color
                rich_print(f"[red]{response.o}[/red]")
            if verbose:
                rich_print(response)
        elif error(response):
            rich_print(response)
        else:
            assert_never(response)

    asyncio.run(f())
