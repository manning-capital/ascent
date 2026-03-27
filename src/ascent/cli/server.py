import cyclopts

server = cyclopts.App(name="server", help="Manage the Ascent server.")


@server.command()
def start(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
    log_level: str = "info",
):
    """Start the Ascent server (API + UI)."""
    import uvicorn

    print(f"Starting Ascent server on http://{host}:{port}")

    if workers > 1 or reload:
        uvicorn.run(
            "ascent.server.main:create_app",
            factory=True,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level=log_level,
        )
    else:
        from ascent.server.main import create_app

        uvicorn.run(
            create_app(),
            host=host,
            port=port,
            log_level=log_level,
        )
