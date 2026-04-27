<p align="center">
    <img src="docs/logo-no-text-300.png" alt="Git Relay Logo" width="300">
</p>

# Git Relay

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)

A tool to synchronize git repos with smart scheduling and systemd integration.

**Git Relay** is a lightweight, non-intrusive tool for synchronizing and backing up your Git repositories. It maintains a central directory of "hubs" (defaulting to `~/githubs`) that serves as a reliable backup for repositories scattered across your local machine and facilitates seamless development across multiple machines.

By automating periodic synchronization, Git Relay gives you peace of mind without getting in your way. It integrates with `systemd` at the user level (no root required) and lets you decide exactly which repositories are synced and how frequently.

## Features

- **Hub-based Synchronization:** Create "Hubs" to periodically fetch commits from repos on the same machine, and optionally sync with remote hubs.
- **Local & Remote Support:** Sync local hubs to remote hubs over SSH.
- **Smart Scanning:** Automatically discovers repos in configured directories and facilitates creation of new hubs for them.
- **Systemd Integration:** Runs sync daemon as systemd service.
- **Interactive Shell:** Provides a dedicated shell interface for quick management.
- **Command Line Interface:** Gives access to all functionality enabling integration in scripts.

## Installation

The recommended way to install Git Relay is in a dedicated virtual environment to keep your system clean.

### 1. Install the package
```bash
# Create and activate a virtual environment
python3 -m venv ~/.local/share/gitrelay-venv
source ~/.local/share/gitrelay-venv/bin/activate

# Install from PyPI
pip install gitrelay
```

### 2. Set up the environment
Once installed and with the virtual environment still active, run these commands to complete the setup:

- **Install CLI links:** Symlinks `gitrelay` to `~/.local/bin` (ensuring it's available without activating the venv) and installs bash autocompletion.
  ```bash
  gitrelay cli install
  ```
- **Initialize configuration:** Initializes configuration with default values.
  ```bash
  gitrelay config init
  ```
- **Install the daemon:** Sets up a `systemd` user service to run the synchronization daemon automatically.
  ```bash
  gitrelay daemon install
  ```

> **Note:** To ensure the background daemon continues running even when you are logged out, you should enable "linger" for your user account:
> ```bash
> loginctl enable-linger $USER
> ```

## Quick Start

*Note: Git Relay is currently in active early development. Usage examples and documentation will be expanded as the CLI matures.*

## Concepts and Terminology

<details>
<summary>Click to expand details about Hubs, Discovery, and Naming Rules</summary>

### Hub
A **Hub** is a bare git repository managed exclusively by `gitrelay`. It acts as the central synchronization point for one or more **Local Repos** and potentially other **Remote Hubs** on different hosts.

- **Local Hub:** A hub located on the local machine, within the configured `hub_dir` (default: `~/githubs`).
- **Remote Hub:** A hub located on a remote host, accessed via SSH. Remote hubs are resolved by retrieving the configured `hub_dir` from `~/.config/gitrelay/main.json` on the remote host; if missing, Git Relay falls back to the `hub_dir` path configured for the local host and, as a final fallback, it will try to resolve using the default `~/githubs`.
- **Hub Name:** Hubs are identified by their relative path from the base `hub_dir`.
- **Hub Namespaces:** Hubs can be organized into subdirectories within the `hub_dir`, up to a configurable maximum depth. Thus a Hub Name may consist of several path components, separated with `/`. The namespace of a hub is thus the path up to and excluding the last path component of a hub name.
     - *Example:* hub name=`work/foo-bar` -> hub namespace=`work`.
- **Hub Path:** A hub's path is `hub_dir` + `Hub Name` + `.git`.
     - *Example:* `work/foo-bar` -> `~/githubs/work/foo-bar.git`.

#### Discovery and Scanning
Git Relay is designed to give you absolute control; **synchronization jobs are never created automatically.** Instead, Git Relay uses an optional scanning process to simplify manual configuration.

- **Intelligent Suggestions:** By periodically scanning local and remote directories, the tool identifies repositories and hubs with shared commit lineage or matching names.
- **Effortless Setup:** Discovered but unsynced hubs and repos are listed within the interface, allowing you to pick targets easily without having to navigate the filesystem manually.
- **Comprehensive Logging:** Scan data is stored in `~/.cache/gitrelay/scan/`. Newly discovered or missing repos and hubs are logged in `log.jsonl`, while
  complete lists of known repos and hubs are kept in `local-repos.jsonl`, `local-hubs.jsonl`, and `remote-hubs.jsonl`.


#### Hub Naming Rules
A **Logical Hub Name** must:
- Use alphanumeric characters, `-`, `_`, `.`, and `/`.
- No path component (part between slashes) can begin or end with a dot (`.`), hyphen (`-`), or underscore (`_`)
    - *Invalid:* `.a/b/c`, `a./b/c`, `a/-b/c`, `1/2/3_`
- No path component may end with '.git' (irrespective of case).
    - *Invalid:* `work.git/foo-bar`, `work/foo-bar.git`, `work/foo-bar.GIT`
- Not start/end with `/` or contain `//`.
    - *Invalid:* `work//foo-bar`, `/work/foo-bar`, `work/foo-bar/`
- Respect `max_namespace_depth` (default: 2) and `max_hub_name_length` (default: 80).

</details>

## Configuration

The recommended way to manage your configuration is through the `gitrelay` command-line interface or the interactive shell.

<details>
<summary>Click to expand details about configuration files</summary>

Git Relay stores its configuration in `~/.config/gitrelay/`. The primary files include:

- `main.json`: General settings for the daemon and CLI.
- `local-hubs.json`: Configuration for locally managed hubs.
- `remote-hosts.json`: Definitions for remote hosts and their hub directories.

*Note: Direct manual editing of these files is possible but not recommended as the CLI provides validation and safety checks.*

</details>

## License

This project is licensed under the GNU General Public License v3 (GPLv3) - see the [LICENSE](LICENSE) file for details.
