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
import click
import subprocess
import os
from typing import Optional
from rich import print
from . import install, daemon

app = typer.Typer(
    help="Git Relay: Synchronize git repositories with smart scheduling.",
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


@install_app.command("bash-completion")
def install_bash_completion():
    """Install bash completion for gitrelay."""
    # We must use the 'gitrelay' command name to ensure Typer generates
    # clean completion filenames (gitrelay.sh)
    exe = install.get_executable_path()
    try:
        # Use the absolute path to the gitrelay executable
        subprocess.run([exe, "--install-completion"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error installing completion: {e}[/red]")
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


# --- Daemon Group ---
daemon_app = typer.Typer(help="Control the background synchronization daemon.")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command("start")
def daemon_start():
    """Start the background synchronization daemon."""
    print("[green]Daemon started.[/green]")
    daemon.daemon_start()


@daemon_app.command("logs")
def daemon_logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output.")
):
    """View the daemon logs via journalctl."""
    cmd = ["journalctl", "--user", "-u", f"{install.SERVICE_NAME}.service"]
    if follow:
        cmd.append("-f")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        # Expected when using -f
        pass


@daemon_app.command("status")
def daemon_status():
    """Show the daemon service status via systemctl."""
    try:
        subprocess.run(
            ["systemctl", "--user", "status", f"{install.SERVICE_NAME}.service"]
        )
    except Exception as e:
        print(f"[red]Error checking status: {e}[/red]")
        raise typer.Exit(code=1)


# --- General Commands ---
@app.command("help")
def show_help(ctx: typer.Context, command: Optional[str] = typer.Argument(None)):
    """Show help for a specific command or an overview of all commands."""
    main_click_group = typer.main.get_command(app)

    if command:
        sub_command = main_click_group.get_command(ctx, command)
        if sub_command:
            print(sub_command.get_help(ctx))
        else:
            print(f"[red]Unknown command: {command}[/red]")
            raise typer.Exit(code=1)
    else:
        print("\n[bold]Git Relay Command Reference[/bold]")
        print("Usage: [bold]gitrelay[/bold] <command> <subcommand>\n")

        # 1. Print General Commands (like help itself)
        help_cmd = main_click_group.get_command(ctx, "help")
        if help_cmd:
            print(
                f"  [green]gitrelay help[/green]{' ' * 9} [dim]{help_cmd.help}[/dim]\n"
            )

        # 2. Print Categorized Groups
        for name, cmd in sorted(main_click_group.commands.items()):
            if name == "help":
                continue

            if isinstance(cmd, click.Group):
                header = cmd.help or f"Manage {name} commands"
                print(f"[italic cyan]{header}:[/italic cyan]")
                for sub_name, sub_cmd in sorted(cmd.commands.items()):
                    full_cmd = f"{name} {sub_name}"
                    sub_help = sub_cmd.help or sub_cmd.short_help or ""
                    print(
                        f"  [green]gitrelay {full_cmd:18}[/green] [dim]{sub_help}[/dim]"
                    )
                print()


def main():
    app()


if __name__ == "__main__":
    main()
