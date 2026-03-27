import cyclopts

from ascent.cli.deploy import deploy
from ascent.cli.seed import seed
from ascent.cli.server import server

app = cyclopts.App(name="ascent", help="Ascent - Trading algorithm framework.")
app.command(server)
app.command(seed)
app.command(deploy)
