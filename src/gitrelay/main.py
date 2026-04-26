# gitrelay: Sync git repos with smart scheduling and systemd integration.
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

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print

from . import daemon, hub, systemd

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="Git Relay: Synchronize git repositories with smart scheduling.",
)


def setup_logging():
    """Configures basic logging to stderr."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


# --- Installation Logic ---


def get_executable_path() -> str:
    """Returns the absolute path to the current gitrelay executable."""
    executable = subprocess.run(
        ["which", "gitrelay"], capture_output=True, text=True
    ).stdout.strip()

    if not executable:
        # Fallback to absolute path of the script if which fails
        executable = str(Path(sys.prefix) / "bin" / "gitrelay")
        if not Path(executable).exists():
            executable = str(Path(sys.argv[0]).absolute())

    return executable


def install_cli_symlink() -> bool:
    """Creates ~/.local/bin/gitrelay symlink pointing to the current executable."""
    target = Path("~/.local/bin/gitrelay").expanduser()
    current_exe = Path(get_executable_path())

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(current_exe)
        logger.info("Successfully created symlink: %s -> %s", target, current_exe)
        return True
    except Exception as e:
        logger.error("Error creating symlink: %s", e)
        return False


def check_cli_symlink() -> bool:
    """Checks if the CLI symlink is correctly installed."""
    target = Path("~/.local/bin/gitrelay").expanduser()
    if not (target.exists() or target.is_symlink()):
        return False

    current_exe = get_executable_path()
    return os.path.realpath(target) == str(current_exe)


def uninstall_cli_symlink() -> bool:
    """Removes ~/.local/bin/gitrelay symlink."""
    target = Path("~/.local/bin/gitrelay").expanduser()
    try:
        if target.exists() or target.is_symlink():
            target.unlink()
            logger.info("Removed symlink: %s", target)
            return True
        else:
            logger.warning("Symlink not found: %s", target)
            return False
    except Exception as e:
        logger.error("Error removing symlink: %s", e)
        return False


# --- CLI Group ---
cli_app = typer.Typer(help="Manage the local CLI environment and shell integration.")
app.add_typer(cli_app, name="cli")


@cli_app.command("install")
def cli_install():
    """Install CLI symlink and shell completion."""
    # 1. Install Symlink
    if install_cli_symlink():
        print("[green]Successfully installed CLI symlink.[/green]")
    else:
        print("[red]Failed to install CLI symlink.[/red]")

    # 2. Install Completion
    exe = get_executable_path()
    try:
        subprocess.run([exe, "--install-completion"], check=True)
        print("[green]Successfully installed shell completion.[/green]")
    except subprocess.CalledProcessError as e:
        print(f"[red]Error installing completion: {e}[/red]")


@cli_app.command("uninstall")
def cli_uninstall():
    """Uninstall CLI symlink and show completion removal instructions."""
    # 1. Uninstall Symlink
    if uninstall_cli_symlink():
        print("[green]Successfully removed CLI symlink.[/green]")
    else:
        print("[yellow]CLI symlink not found or could not be removed.[/yellow]")

    # 2. Instructions for Completion
    home = Path.home()
    completion_script = home / ".bash_completions" / "gitrelay.sh"
    print("\n[bold]Manual Completion Uninstall Instructions:[/bold]")
    print("1. Open your shell config file (e.g., [bold]~/.bashrc[/bold]).")
    print("2. Remove the line that sources the gitrelay completion script:")
    print(f"   [dim]source '{completion_script}'[/dim]")
    print(f"3. Delete the script file: [bold]{completion_script}[/bold]")
    print("4. Restart your terminal.\n")


# --- Hub Group ---
hub_app = typer.Typer(help="Manage local hubs (bare git repositories).")
app.add_typer(hub_app, name="hub")


@hub_app.command("init")
def hub_init(
    name: str = typer.Argument(..., help="The name of the hub to initialize."),
):
    """Initialize a new local bare git repository (hub)."""
    try:
        path = hub.init_hub(name)
        print(f"[green]Successfully initialized hub: {name}[/green]")
        print(f"[dim]Path: {path}[/dim]")
    except FileNotFoundError:
        print("[red]Main configuration not found.[/red]")
        print("Please run [bold]gitrelay config init[/bold] first.")
        raise typer.Exit(code=1)
    except FileExistsError as e:
        print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"[red]Failed to initialize hub: {e}[/red]")
        raise typer.Exit(code=1)


@hub_app.command("delete")
def hub_delete(
    name: str = typer.Argument(..., help="The name of the hub to delete."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Do not ask for confirmation."
    ),
):
    """Delete a local bare git repository (hub) and its logs."""
    if not yes:
        typer.confirm(
            f"Are you sure you want to delete hub '{name}' and all its logs?",
            abort=True,
        )

    try:
        hub.delete_hub(name)
        print(f"[green]Successfully deleted hub: {name}[/green]")
    except FileNotFoundError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"[red]Failed to delete hub: {e}[/red]")
        raise typer.Exit(code=1)


# --- Config Group ---
config_app = typer.Typer(help="Manage Git Relay configuration.")
app.add_typer(config_app, name="config")


@config_app.command("init")
def config_init(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing configuration."
    )
):
    """Initialize default configuration files."""
    from .config import HostsConfig, LocalHubsConfig, MainConfig

    configs = [
        ("Main configuration", MainConfig),
        ("Local hubs configuration", LocalHubsConfig),
        ("Remote hosts configuration", HostsConfig),
    ]

    for label, cls in configs:
        path = cls.get_config_path().expanduser()
        if path.exists() and not force:
            print(f"[yellow]{label} already exists at {path}[/yellow]")
            continue

        try:
            cls().save()
            print(f"[green]Successfully initialized {label} at {path}[/green]")
        except Exception as e:
            print(f"[red]Failed to initialize {label}: {e}[/red]")


# --- Daemon Group ---
daemon_app = typer.Typer(help="Control the background synchronization daemon.")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command("run")
def daemon_run(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulator mode: don't perform actual sync."
    )
):
    """Execute the daemon synchronization loop."""
    daemon.daemon_start(dry_run=dry_run)


@daemon_app.command("install")
def daemon_install(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Install service in dry-run (simulator) mode."
    )
):
    """Install and start the systemd user service."""
    if systemd.install_service(dry_run=dry_run):
        print("[green]Successfully installed and started systemd service.[/green]")
    else:
        print("[red]Failed to install systemd service.[/red]")
        raise typer.Exit(code=1)


@daemon_app.command("uninstall")
def daemon_uninstall():
    """Disable and remove the systemd user service."""
    if systemd.uninstall_service():
        print("[green]Successfully uninstalled systemd service.[/green]")
    else:
        print("[yellow]Systemd service not found or could not be removed.[/yellow]")


@daemon_app.command("start")
def daemon_start():
    """Start the background synchronization daemon via systemd."""
    try:
        systemd.start_service()
        print("[green]Daemon service started.[/green]")
    except Exception as e:
        print(f"[red]Error starting daemon: {e}[/red]")
        raise typer.Exit(code=1)


@daemon_app.command("stop")
def daemon_stop():
    """Stop the background synchronization daemon via systemd."""
    try:
        systemd.stop_service()
        print("[green]Daemon service stopped.[/green]")
    except Exception as e:
        print(f"[red]Error stopping daemon: {e}[/red]")
        raise typer.Exit(code=1)


@daemon_app.command("restart")
def daemon_restart():
    """Restart the background synchronization daemon via systemd."""
    try:
        systemd.restart_service()
        print("[green]Daemon service restarted.[/green]")
    except Exception as e:
        print(f"[red]Error restarting daemon: {e}[/red]")
        raise typer.Exit(code=1)


@daemon_app.command("enable")
def daemon_enable():
    """Enable the background synchronization daemon to start on login."""
    try:
        systemd.enable_service(now=False)
        print("[green]Daemon service enabled.[/green]")
    except Exception as e:
        print(f"[red]Error enabling daemon: {e}[/red]")
        raise typer.Exit(code=1)


@daemon_app.command("disable")
def daemon_disable():
    """Disable the background synchronization daemon from starting on login."""
    try:
        systemd.disable_service(now=False)
        print("[green]Daemon service disabled.[/green]")
    except Exception as e:
        print(f"[red]Error disabling daemon: {e}[/red]")
        raise typer.Exit(code=1)


@daemon_app.command("logs")
def daemon_logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output."),
    since: Optional[str] = typer.Option(
        None, "--since", "-s", help="Show logs since a specific time (e.g. '1h ago')."
    ),
    output: str = typer.Option(
        "short", "--output", "-o", help="Journalctl output format (short, cat, etc.)."
    ),
):
    """View the daemon logs via journalctl."""
    cmd = ["journalctl", "--user", "-u", f"{systemd.get_service_name()}.service"]
    if follow:
        cmd.append("-f")
    if since:
        cmd.extend(["--since", since])
    if output:
        cmd.extend(["--output", output])
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        # Expected when using -f
        pass


@daemon_app.command("status")
def daemon_status():
    """Show the daemon service status via systemctl."""
    try:
        print(systemd.get_service_status())
    except Exception as e:
        print(f"[red]Error checking status: {e}[/red]")
        raise typer.Exit(code=1)


# --- General Commands ---
@app.command("help")
def show_help(ctx: typer.Context, command: Optional[str] = typer.Argument(None)):
    """Show help for a specific command or an overview of all commands."""
    import click

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

        # 1. Print General Commands
        help_cmd = main_click_group.get_command(ctx, "help")
        if help_cmd:
            h_text = help_cmd.help or ""
            print(f"  [green]gitrelay help[/green]{' ' * 13} [dim]{h_text}[/dim]\n")

        # 2. Calculate max width for alignment
        def get_commands(click_group, prefix=""):
            cmds = []
            for name, cmd in click_group.commands.items():
                if name == "help":
                    continue
                if isinstance(cmd, click.Group):
                    cmds.extend(get_commands(cmd, prefix=f"{prefix}{name} "))
                else:
                    cmds.append(f"{prefix}{name}")
            return cmds

        all_cmds = get_commands(main_click_group)
        max_width = max(len(c) for c in all_cmds) if all_cmds else 20

        # 3. Print Categorized Groups
        for name, cmd in sorted(main_click_group.commands.items()):
            if name == "help":
                continue

            if isinstance(cmd, click.Group):
                header = cmd.help or f"Manage {name} commands"
                # Strip trailing period ONLY for header use
                header = header.rstrip(".") + ":"
                print(f"[italic cyan]{header}[/italic cyan]")

                def print_group_commands(click_group, prefix):
                    for sub_name, sub_cmd in sorted(click_group.commands.items()):
                        if isinstance(sub_cmd, click.Group):
                            print_group_commands(sub_cmd, prefix=f"{prefix}{sub_name} ")
                        else:
                            full_cmd = f"{prefix}{sub_name}"
                            s_help = sub_cmd.help or sub_cmd.short_help or ""
                            # Format line with dynamic padding
                            cmd_str = f"  [green]gitrelay {full_cmd:<{max_width}}[/green]"
                            print(f"{cmd_str} [dim]{s_help}[/dim]")

                print_group_commands(cmd, prefix=f"{name} ")
                print()


def main():
    setup_logging()
    app()


if __name__ == "__main__":
    main()
