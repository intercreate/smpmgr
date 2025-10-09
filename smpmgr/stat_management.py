import asyncio
from typing import cast

import typer
from rich import print
from rich.table import Table
from smpclient.requests.statistics_management import GroupData, ListOfGroups

from smpmgr.common import Options, connect_with_spinner, get_smpclient, smp_request

app = typer.Typer(name="statistics", help="The SMP stat Management Group.")


@app.command(name="list")
def list_stats(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show raw packet data"),
) -> None:
    """Request that the SMP Server list all available statistics groups."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, ListOfGroups())  # type: ignore

        if verbose:
            print(r)
        else:
            if hasattr(r, 'stat_list') and r.stat_list:
                table = Table(title="Statistics Groups")
                table.add_column("Group Name", style="cyan")
                table.add_column("Number of Groups", style="green")

                for group_name in r.stat_list:
                    table.add_row(group_name, str(len(r.stat_list)))

                print(table)
            else:
                print("No statistics groups available")

    asyncio.run(f())


@app.command(name="smp_svr_stats")
def smp_svr_stats(ctx: typer.Context) -> None:
    """Request statistics related to the SMP server itself."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, GroupData(name="smp_svr_stats"))
        print(r)

    asyncio.run(f())


@app.command(name="get")
def get_group(
    ctx: typer.Context, group_id: str = typer.Argument(..., help="The statistics group ID to fetch")
) -> None:
    """Fetch a specific statistics group by group id."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)
        r = await smp_request(smpclient, options, GroupData(name=group_id))
        print(r)

    asyncio.run(f())


@app.command(name="fetch-all")
def fetch_all_groups(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show raw packet data"),
) -> None:
    """Fetch all statistics groups and their data."""

    options = cast(Options, ctx.obj)
    smpclient = get_smpclient(options)

    async def f() -> None:
        await connect_with_spinner(smpclient, options.timeout)

        list_response = await smp_request(smpclient, options, ListOfGroups())  # type: ignore

        if not hasattr(list_response, 'stat_list') or not list_response.stat_list:
            print("No statistics groups available")
            return

        groups_data = []

        for group_name in list_response.stat_list:
            group_data = await smp_request(smpclient, options, GroupData(name=group_name))
            groups_data.append({'name': group_name, 'data': group_data})

        if verbose:
            for group_info in groups_data:
                print(f"\n=== Group: {group_info['name']} ===")
                print("Data:")
                print(group_info['data'])
        else:
            table = Table(title="All Statistics Groups Data")
            table.add_column("Group Name", style="cyan")
            table.add_column("Data Available", style="yellow")

            for group_info in groups_data:
                group_name = str(group_info['name'])
                data_available = "Yes" if group_info['data'] else "No"
                table.add_row(group_name, data_available)

            print(table)

            print("\n=== Detailed Group Data ===")
            for group_info in groups_data:
                print(f"\n[bold cyan]Group: {group_info['name']}[/bold cyan]")
                print("Data:")
                print(group_info['data'])

    asyncio.run(f())
