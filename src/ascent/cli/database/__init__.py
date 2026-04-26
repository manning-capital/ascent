"""Database lifecycle commands: seed + targeted clear operations."""

import cyclopts

from ascent.cli.seed import seed as seed_app

database = cyclopts.App(name="database", help="Database lifecycle operations.")
database.command(seed_app)


@database.command(name="clear-trades")
def clear_trades(*, server_url: str = "http://localhost:8000") -> None:
    """Delete all trades, trade legs, orders, and their statuses.

    Also truncates the event outbox so no stale dispatch intents from
    cleared trades get replayed.

    Parameters
    ----------
    server_url
        Base URL of the running Ascent server.
    """
    from rich.console import Console

    from ascent.client import AscentClient

    console = Console(stderr=True)
    client = AscentClient(server_url)

    with console.status("[bold cyan]Waiting for server...[/]"):
        client.wait_until_ready()

    with console.status("[bold yellow]Clearing trades, legs, orders, statuses, outbox...[/]"):
        client.clear_trades()
    console.print("[green]✓[/] Trades cleared")
    client.close()


@database.command(name="clear-holdings")
def clear_holdings(*, server_url: str = "http://localhost:8000") -> None:
    """Delete all portfolio asset holdings.

    Parameters
    ----------
    server_url
        Base URL of the running Ascent server.
    """
    from rich.console import Console

    from ascent.client import AscentClient

    console = Console(stderr=True)
    client = AscentClient(server_url)

    with console.status("[bold cyan]Waiting for server...[/]"):
        client.wait_until_ready()

    with console.status("[bold yellow]Clearing portfolio holdings...[/]"):
        client.clear_holdings()
    console.print("[green]✓[/] Holdings cleared")
    client.close()
