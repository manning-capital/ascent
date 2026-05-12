import cyclopts

seed = cyclopts.App(name="seed", help="Seed the database with sample data.")


@seed.command()
def run(
    *,
    server_url: str = "http://localhost:8000",
    drop: bool = False,
    profile: str = "full",
):
    """Load fake data into the database for UI testing.

    Parameters
    ----------
    server_url
        Base URL of the running Ascent server.
    drop
        If True, instructs the user to restart the server with --drop first.
    profile
        Which seed profile to run.  Options:

        - ``full`` (default) — everything including feeds, strategies,
          exchanges, and trades.
        - ``base`` — types, assets, descriptors, metadata, providers,
          instruments, and composites only (no feeds, strategies,
          exchanges, or trades).
    """
    import datetime
    import os
    import sys
    import time

    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table

    from ascent.cli.seed.assets import seed_assets
    from ascent.cli.seed.composites import seed_composites
    from ascent.cli.seed.descriptors import seed_descriptors
    from ascent.cli.seed.feeds import seed_feeds
    from ascent.cli.seed.instruments import seed_instruments
    from ascent.cli.seed.metadata import seed_asset_metadata
    from ascent.cli.seed.providers import seed_providers
    from ascent.cli.seed.strategies import seed_strategies
    from ascent.cli.seed.trades import seed_trades
    from ascent.cli.seed.type_metadata import seed_type_metadata
    from ascent.cli.seed.types import seed_types
    from ascent.client import AscentClient

    # All rich output goes to stderr; stdout is silenced to suppress
    # print() calls from individual seed functions.
    console = Console(stderr=True)

    client = AscentClient(server_url)

    with console.status("[bold cyan]Waiting for server...[/]"):
        client.wait_until_ready()
    console.print("[green]✓[/] Server is ready")

    if drop:
        with console.status("[bold yellow]Dropping and recreating all tables...[/]"):
            client.reset_database()
        console.print("[green]✓[/] Database reset complete")

    existing = client.get_asset_types()
    if existing:
        console.print("[red]✗[/] Database already has data. Use --drop to reset first.")
        return

    now = datetime.datetime.now(datetime.UTC)
    ctx: dict = {"now": now}

    valid_profiles = ("full", "base")
    if profile not in valid_profiles:
        console.print(
            f"[red]✗[/] Unknown profile '{profile}'. Choose from: {', '.join(valid_profiles)}"
        )
        return

    base_steps = [
        ("Type hierarchies", seed_types),
        ("Assets", seed_assets),
        ("Attributes & metadata types", seed_descriptors),
        ("Type-metadata fields", seed_type_metadata),
        ("Asset metadata", seed_asset_metadata),
        ("Providers & exchanges", seed_providers),
        ("Instruments", seed_instruments),
        ("Composites", seed_composites),
    ]

    full_steps = [
        ("Feeds, runs & partitions", seed_feeds),
        ("Strategies & runs", seed_strategies),
        ("Trades, orders & snapshots", seed_trades),
    ]

    steps = base_steps if profile == "base" else base_steps + full_steps

    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    ctx["progress"] = progress

    console.print()
    total_start = time.time()

    # Redirect stdout to /dev/null so print() calls from seed functions
    # are silenced. Rich writes to stderr via console so it's unaffected.
    _saved_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")

    try:
        with progress:
            for i, (label, fn) in enumerate(steps, 1):
                step_start = time.time()
                tag = f"[dim]({i}/{len(steps)})[/]"
                step_task = progress.add_task(
                    f"⠋ {tag} [bold blue]{label}[/]",
                    total=None,
                )
                fn(client, ctx)
                elapsed = time.time() - step_start
                progress.update(step_task, completed=1, total=1)
                progress.update(
                    step_task,
                    description=f"[green]✓[/] {tag} {label} [dim]({elapsed:.1f}s)[/]",
                )
    finally:
        sys.stdout.close()
        sys.stdout = _saved_stdout

    total_elapsed = time.time() - total_start
    client.close()

    # Summary table
    console.print()
    table = Table(title="Seed Summary", show_lines=False, title_style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Asset types", "16 (4 top-level + subtypes)")
    table.add_row("Assets", str(len(ctx["asset_by_symbol"])))
    table.add_row("Metadata types", str(len(ctx["meta"])))
    table.add_row("Providers", "4")
    table.add_row("Exchanges", "5")
    table.add_row("Portfolios", "5")
    table.add_row("Instrument types", "5 (hierarchical)")
    table.add_row("Instruments", str(len(ctx["all_instruments"])))
    table.add_row("Composite types", "8 (hierarchical)")
    table.add_row("Composites", str(len(ctx["all_composites"])))
    if profile == "full":
        table.add_row("Feeds", str(len(ctx["all_feeds"])))
        table.add_row("Instrument attributes", f"{ctx['paga_count']:,}")
        table.add_row("Composite attributes", f"{ctx['comp_count']:,}")
        table.add_row("Strategies", str(len(ctx["strategy_objs"])))
        table.add_row("Strategy-run / feed-run links", str(ctx["link_count"]))
        table.add_row("Trades", str(len(ctx["all_trades"])))

    console.print(table)
    console.print(f"\n[bold green]✓ Seeded successfully in {total_elapsed:.1f}s[/]")
