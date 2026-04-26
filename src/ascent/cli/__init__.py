import cyclopts

from ascent.cli.database import database
from ascent.cli.deploy import deploy
from ascent.cli.server import server

app = cyclopts.App(name="ascent", help="Ascent - Trading algorithm framework.")
app.command(server)
app.command(database)
app.command(deploy)
