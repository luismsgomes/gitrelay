# gitrelay: A tool to synchronize git repos with smart scheduling and systemd integration.
# Copyright (C) 2026  Luís Gomes
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import typer
from rich import print
from . import install

app = typer.Typer(
    help="Git Relay: Synchronize git repositories with smart scheduling.",
    add_completion=False,
)

# --- Install Group ---
install_app = typer.Typer(help="Manage Git Relay installation and system integration.")
app.add_typer(install_app, name="install")


@install_app.command("symlink")
def install_symlink():
    """Create ~/.local/bin/gitrelay symlink."""
    if install.install_cli_symlink():
        print("[green]Successfully installed CLI symlink.[/green]")
    else:
        print("[red]Failed to install CLI symlink.[/red]")
        raise typer.Exit(code=1)


@install_app.command("service")
def install_service():
    """Install and start the systemd user service."""
    if install.install_systemd_service():
        print("[green]Successfully installed and started systemd service.[/green]")
    else:
        print("[red]Failed to install systemd service.[/red]")
        raise typer.Exit(code=1)


# --- Uninstall Group ---
uninstall_app = typer.Typer(help="Remove Git Relay components from the system.")
app.add_typer(uninstall_app, name="uninstall")


@uninstall_app.command("symlink")
def uninstall_symlink():
    """Remove ~/.local/bin/gitrelay symlink."""
    if install.uninstall_cli_symlink():
        print("[green]Successfully removed CLI symlink.[/green]")
    else:
        print("[yellow]CLI symlink not found or could not be removed.[/yellow]")


@uninstall_app.command("service")
def uninstall_service():
    """Disable and remove the systemd user service."""
    if install.uninstall_systemd_service():
        print("[green]Successfully uninstalled systemd service.[/green]")
    else:
        print("[yellow]Systemd service not found or could not be removed.[/yellow]")


def main():
    app()


if __name__ == "__main__":
    main()
