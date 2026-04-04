import cyclopts

seed = cyclopts.App(name="seed", help="Seed the database with sample data.")


@seed.command()
def run(
    *,
    server_url: str = "http://localhost:8000",
    drop: bool = False,
):
    """Load fake data into the database for UI testing.

    Parameters
    ----------
    server_url
        Base URL of the running Ascent server.
    drop
        If True, instructs the user to restart the server with --drop first.
    """
    import datetime

    from ascent.cli.seed.assets import seed_assets
    from ascent.cli.seed.composites import seed_composites
    from ascent.cli.seed.descriptors import seed_descriptors
    from ascent.cli.seed.feeds import seed_feeds
    from ascent.cli.seed.instruments import seed_instruments
    from ascent.cli.seed.metadata import seed_asset_metadata
    from ascent.cli.seed.portfolios import seed_portfolios
    from ascent.cli.seed.providers import seed_providers
    from ascent.cli.seed.strategies import seed_strategies
    from ascent.cli.seed.trades import seed_trades
    from ascent.cli.seed.type_metadata import seed_type_metadata
    from ascent.cli.seed.types import seed_types
    from ascent.client import AscentClient

    client = AscentClient(server_url)

    print("Waiting for server...")
    client.wait_until_ready()
    print("Server is ready.")

    if drop:
        print("Dropping and recreating all tables...")
        client.reset_database()
        print("Database reset complete.")

    existing = client.get_asset_types()
    if existing:
        print("Database already has data. Use --drop to reset first.")
        return

    now = datetime.datetime.now(datetime.UTC)
    ctx: dict = {"now": now}

    seed_types(client, ctx)
    seed_assets(client, ctx)
    seed_descriptors(client, ctx)
    seed_type_metadata(client, ctx)
    seed_asset_metadata(client, ctx)
    seed_providers(client, ctx)
    seed_portfolios(client, ctx)
    seed_instruments(client, ctx)
    seed_composites(client, ctx)
    seed_feeds(client, ctx)
    seed_strategies(client, ctx)
    seed_trades(client, ctx)

    client.close()

    print("\nSeeded successfully:")
    print("  16 asset types (4 top-level with hierarchical subtypes)")
    print(f"  {len(ctx['asset_by_symbol'])} assets across all asset classes")
    print(f"  {len(ctx['meta'])} metadata types")
    print(f"  {len(ctx['all_feeds'])} feeds")
    print(f"  5 instrument types (hierarchical), {len(ctx['all_instruments'])} instruments")
    print(f"  8 composite types (hierarchical), {len(ctx['all_composites'])} composites")
    print(
        f"  {ctx['paga_count']} instrument_attribute rows, {ctx['comp_count']} composite_attribute rows"
    )
    print(f"  {len(ctx['strategy_objs'])} strategies (10 strategy types)")
    print(f"  {ctx['link_count']} strategy-run <-> feed-run links")
    print(f"  {len(ctx['all_trades'])} trades")
    print("  5 portfolios, 4 providers, 5 exchanges")
