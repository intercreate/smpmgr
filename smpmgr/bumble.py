"""Bumble BLE transport subcommands: scan, pair, bonds, firmware."""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Final, cast

import typer
from rich import print
from rich.table import Table
from smpclient.transport.bumble import SMPBumbleTransport
from smpclient.transport.bumble.pairing import (
    PairingAlreadyBonded,
    PairingFailed,
    PairingResult,
    PairingSucceeded,
    PairingTimedOut,
    pair_device,
)
from smpclient.transport.bumble.scan import ScanAll, ScanForName, ScanMode
from typing_extensions import Annotated, assert_never

from smpmgr.common import Options, build_pair_delegate, resolve_keystore_strategy

logger = logging.getLogger(__name__)

app: Final = typer.Typer(
    name="bumble",
    help="Bumble BLE transport: scan, pair, bonds, firmware.",
    no_args_is_help=True,
)
bonds_app: Final = typer.Typer(
    name="bonds",
    help="Manage bumble keystore bonds.",
    no_args_is_help=True,
)
firmware_app: Final = typer.Typer(
    name="firmware",
    help="Bundled Zephyr HCI controller firmware.",
    no_args_is_help=True,
)
app.add_typer(bonds_app)
app.add_typer(firmware_app)


def _scan_mode(name: str | None) -> ScanMode:
    return ScanForName(name=name) if name is not None else ScanAll()


@app.command(name="scan")
def scan(
    ctx: typer.Context,
    timeout: Annotated[float, typer.Option(help="Scan duration in seconds.")] = 5.0,
    name: Annotated[
        str | None,
        typer.Option(help="Match advertised local name; returns eagerly on first hit."),
    ] = None,
    all_devices: Annotated[
        bool,
        typer.Option("--all", help="Show every advertiser, not just SMP servers."),
    ] = False,
) -> None:
    """Scan for advertising BLE devices via the bumble HCI controller."""

    options = cast(Options, ctx.obj)

    async def f() -> None:
        results = await SMPBumbleTransport.scan(
            hci=options.hci, timeout_s=timeout, mode=_scan_mode(name)
        )
        if not all_devices:
            results = tuple(r for r in results if r.has_smp_service)
        if not results:
            print("[yellow]No devices found.[/yellow]")
            raise typer.Exit(code=1)

        table = Table(title="Advertising devices")
        table.add_column("Address")
        table.add_column("Name")
        table.add_column("RSSI", justify="right")
        table.add_column("SMP", justify="center")
        for r in results:
            table.add_row(
                r.address,
                r.name or "[dim]<unnamed>[/dim]",
                str(r.rssi) if r.rssi is not None else "",
                "[green]yes[/green]" if r.has_smp_service else "[dim]no[/dim]",
            )
        print(table)

    asyncio.run(f())


def _report_pairing_result(result: PairingResult) -> int:
    match result:
        case PairingSucceeded(bonded):
            print(f"[green]Pairing succeeded[/green] (bonded={bonded}).")
            return 0
        case PairingAlreadyBonded():
            print("[yellow]Already bonded[/yellow]; nothing to do. Use --force to re-pair.")
            return 0
        case PairingTimedOut(elapsed_s):
            print(f"[red]Pairing timed out[/red] after {elapsed_s:.1f}s.")
            return 1
        case PairingFailed(reason, detail):
            print(f"[red]Pairing failed[/red]: {reason.value}: {detail}")
            return 1
        case _ as unreachable:
            assert_never(unreachable)


@app.command(name="pair")
def pair_cmd(
    ctx: typer.Context,
    address: Annotated[
        str,
        typer.Argument(help="BD_ADDR or advertised local name of the peer to bond with."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Delete any existing local bond first and pair from scratch."),
    ] = False,
    scan_timeout: Annotated[
        float,
        typer.Option(help="Scan timeout in seconds when `address` is a local name."),
    ] = 10.0,
) -> None:
    """Connect, pair (PIN-entry by default), disconnect — pre-bonds a peer."""

    options = cast(Options, ctx.obj)
    delegate = build_pair_delegate(options.pair_on_connect)
    if delegate is None:
        print(
            "[red]--pair-on-connect=none is incompatible with [bold]bumble pair[/bold];"
            " choose 'keyboard', 'display', or 'nio'.[/red]"
        )
        raise typer.Exit(code=1)

    async def f() -> int:
        result = await pair_device(
            address,
            delegate,
            hci=options.hci,
            keystore=resolve_keystore_strategy(options.keystore),
            scan_timeout_s=scan_timeout,
            pair_timeout_s=options.pair_timeout_s,
            force=force,
        )
        return _report_pairing_result(result)

    raise typer.Exit(code=asyncio.run(f()))


def _standalone_transport(options: Options) -> SMPBumbleTransport:
    return SMPBumbleTransport(
        hci=options.hci,
        keystore=resolve_keystore_strategy(options.keystore),
    )


@bonds_app.command(name="list")
def bonds_list(ctx: typer.Context) -> None:
    """List BD_ADDRs currently bonded in the active keystore."""

    options = cast(Options, ctx.obj)

    async def f() -> None:
        bonded = await _standalone_transport(options).bonded_devices()
        if not bonded:
            print("[dim]No bonds in keystore.[/dim]")
            return
        table = Table(title=f"Bonded devices ({options.keystore})")
        table.add_column("Address")
        for addr in bonded:
            table.add_row(addr)
        print(table)

    asyncio.run(f())


@bonds_app.command(name="clear")
def bonds_clear(
    ctx: typer.Context,
    address: Annotated[str, typer.Argument(help="BD_ADDR of the bond to delete.")],
) -> None:
    """Delete the bond for one peer from the keystore."""

    options = cast(Options, ctx.obj)

    async def f() -> None:
        await _standalone_transport(options).clear_bond(address)
        print(f"[green]Cleared bond[/green] for {address}.")

    asyncio.run(f())


@bonds_app.command(name="clear-all")
def bonds_clear_all(
    ctx: typer.Context,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    """Delete every bond from the keystore."""

    options = cast(Options, ctx.obj)

    if not yes and not typer.confirm(
        f"Delete every bond in keystore '{options.keystore}'?", default=False
    ):
        raise typer.Exit(code=1)

    async def f() -> None:
        await _standalone_transport(options).clear_bonds()
        print("[green]Cleared all bonds.[/green]")

    asyncio.run(f())


def _register_firmware_command(parent: typer.Typer, name: str, mod: 'FirmwareModule') -> None:
    """Register one subcommand per typed firmware variant on `parent`.

    Default action with no flags: print the absolute .hex path to stdout —
    designed for shell composition, e.g.
    `west flash --hex-file=$(smpmgr bumble firmware nrf52840dk_default)`.

    Pass `--extract <PATH>` to copy the bundled .hex out to a destination
    (useful when running from the portable binary where the bundle is opaque).
    """
    short_help: Final = f"Board {mod.BOARD}, build {mod.OPTIONS}, sha256={mod.HEX_SHA256[:8]}…"

    @parent.command(name=name, help=short_help)
    def _fw(
        extract: Annotated[
            Path | None,
            typer.Option(
                "--extract",
                help="Copy the .hex out to this path (parent dir auto-created).",
            ),
        ] = None,
        verify: Annotated[
            bool,
            typer.Option(
                "--verify/--no-verify",
                help="Verify the embedded SHA-256 before copying"
                " (only meaningful with --extract).",
            ),
        ] = True,
    ) -> None:
        if extract is None:
            typer.echo(str(mod.HEX_PATH))
            return
        if verify:
            try:
                mod.read_firmware_bytes()
            except ValueError as e:
                typer.echo(f"SHA-256 verification failed: {e}", err=True)
                raise typer.Exit(code=1) from e
        extract.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(mod.HEX_PATH, extract)
        typer.echo(f"Wrote {extract} ({mod.HEX_PATH.stat().st_size} bytes)", err=True)


try:
    from smpclient.transport.firmware.hci import Firmware, firmware
    from zephyr_4_4_0_hci import FirmwareModule

    for _name in Firmware._fields:
        _register_firmware_command(firmware_app, _name, getattr(firmware, _name))
except ImportError:

    @firmware_app.callback(invoke_without_command=True)
    def _firmware_unavailable(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        print(
            "[red]Bundled HCI firmware is not installed.[/red]"
            " Reinstall smpclient with the [bold]hci_firmware[/bold] extra."
        )
        raise typer.Exit(code=1)
