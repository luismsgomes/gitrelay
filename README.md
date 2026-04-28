<p align="center">
    <img src="docs/logo-no-text-300.png" alt="Git Relay Logo" width="300">
</p>

> [!CAUTION]
> **Git Relay is currently in active early development.** Most functionality is still unreliable and may lead to data loss. **DO NOT** install or use this software for production or important repositories yet.

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
- **Background Daemon:** A `systemd`-integrated daemon handles periodic synchronization, repository scanning, and ensures hooks are correctly installed.
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

### 2. Initial Git Relay setup
Once installed and with the virtual environment still active, run these commands to complete the setup:

```bash
gitrelay cli install
gitrelay config init
gitrelay daemon install
```

**What these commands do:**
- **cli install:** Symlinks `gitrelay` to `~/.local/bin` (making it available globally without activating the venv) and installs bash autocompletion.
- **config init:** Initializes your configuration with default values in `~/.config/gitrelay/`.
- **daemon install:** Sets up a `systemd` user service to run the synchronization daemon automatically.

> **Note:** To ensure the background daemon continues running even when you are logged out, you should enable "linger" for your user account (requires root privileges):
> ```bash
> sudo loginctl enable-linger $USER
> ```

## Quick Start

*Note: Git Relay is currently in active early development. Usage examples and documentation will be expanded as the CLI matures.*

## Hubs

A **Hub** is a bare git repository managed exclusively by `gitrelay`. It acts as the central synchronization point for one or more **Local Repos** and potentially other **Remote Hubs** on different hosts.

- **Local Hub:** A hub located on the local machine, within the configured `hub_dir` (default: `~/githubs`).
- **Remote Hub:** A hub located on a remote host, accessed via SSH. Remote hubs are resolved by retrieving the configured `hub_dir` from `~/.config/gitrelay/main.json` on the remote host; if missing, Git Relay falls back to the `hub_dir` path configured for the local host and, as a final fallback, it will try to resolve using the default `~/githubs`.
- **Hub Name:** Hubs are identified by their relative path from the base `hub_dir`.
- **Hub Namespaces:** Hubs can be organized into subdirectories within the `hub_dir`, up to a configurable maximum depth. Thus a Hub Name may consist of several path components, separated with `/`. The namespace of a hub is thus the path up to and excluding the last path component of a hub name.
     - *Example:* hub name=`work/foo-bar` -> hub namespace=`work`.
- **Hub Path:** A hub's path is `hub_dir` + `Hub Name` + `.git`.
     - *Example:* `work/foo-bar` -> `~/githubs/work/foo-bar.git`.

<details>
<summary>Click to expand technical details about Hub Naming Rules</summary>

### Hub Naming Rules
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

## The Relay Algorithm

Git Relay is built around the concept of **Relay Sequences**—the automated propagation of commits across your connected repositories and hubs. Unlike periodic synchronization, relay sequences are synchronous events triggered by user actions.

### The Push-Relay
When you are ready to share or back up your work, you initiate a **Push-Relay** via `git relay push` (or `gitrelay push`):
1. **Local Handoff:** Your commits are pushed from your working repository to your **Local Hub**.
2. **Immediate Propagation:** A `post-receive` hook in the Local Hub immediately "relays" the new commits to all configured **Remote Hubs**.
3. **Synchronization:** Your work is now safely backed up and available for other machines to pull.

<details>
<summary>Click to see technical details of the Push-Relay mechanism</summary>

#### Execution Modes
The `gitrelay push` command operates in two modes, controlled by the `--wait` or `--no-wait` flags:
- **Wait Mode (`--wait`):** The CLI waits for all remote hubs to be updated before returning.
- **No-Wait Mode (`--no-wait`):** The CLI returns as soon as the local hub receives the commits; remote propagation happens in the background.

If neither flag is provided, Git Relay follows a configuration hierarchy to determine the default behavior:
1. **Repository Config:** `default_push_relay_wait` for the specific repository.
2. **Hub Config:** `default_push_relay_wait` for the local hub.
3. **Global Config:** `default_push_relay_wait` in `MainConfig` (defaults to `True`).

#### Implementation
When you execute a push, Git Relay sets the `GITRELAY_HOOK_WAIT` environment variable and executes `git push hub`. The `post-receive` hook in the Local Hub reads this variable:
- If `true`, it runs `gitrelay hook post-receive` in the foreground.
- If `false`, it triggers it in the background.

The `hook post-receive` command loads the hub configuration and pushes the new commits to each configured remote hub. This propagation is performed in parallel or sequentially based on the `parallel_push` setting (configured at the Hub or Global level, defaulting to `True`).

</details>

### The Pull-Relay
To ensure you are working with the most recent state, you initiate a **Pull-Relay** via `git relay pull` (or `gitrelay pull`):
1. **Upstream Fetch:** Git Relay first reaches out to all configured **Remote Hubs** and fetches any new commits into your **Local Hub**.
2. **Local Update:** Once the Local Hub is fresh, Git Relay performs a standard `git pull` from the Hub into your active repository.
3. **Consolidation:** Your local repository is now synchronized with the entire relay network.

*Note: These operations specifically target the "hub" remote. By using the `relay` alias, your standard Git workflow remains intact while benefiting from multi-host synchronization.*

## Periodic Synchronization

In addition to the explicit Relay Sequences, Git Relay provides background periodic synchronization managed by the `gitrelay daemon`. This is essential for machines behind NAT that cannot receive incoming Push-Relays, and as an automated safety net to keep your local environment up-to-date.

Periodic synchronization is particularly useful when working on remote servers. For example, if you are developing on a remote machine and make several commits, Git Relay will periodically fetch those commits into your local hub. This ensures you have a fresh, automated backup of your remote work on your local machine, without requiring you to manually initiate a pull every time you switch back to your local repository.

Git Relay is designed to give you absolute control; **periodic synchronization jobs are never created automatically.** Instead, Git Relay uses an optional scanning process to simplify manual configuration.

<details>
<summary>Click to expand details about Scanning and Discovery</summary>

- **Intelligent Suggestions:** By periodically scanning local and remote directories, the tool identifies repositories and hubs with shared commit lineage or matching names.
- **Effortless Setup:** Discovered but unsynced hubs and repos are listed within the interface, allowing you to pick targets easily without having to navigate the filesystem manually.
- **Comprehensive Logging:** Scan data is stored in `~/.cache/gitrelay/scan/`. Newly discovered or missing repos and hubs are logged in `log.jsonl`, while complete lists of known repos and hubs are kept in `local-repos.jsonl`, `local-hubs.jsonl`, and `remote-hubs.jsonl`.

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
