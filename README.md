<p align="center">
  <img src="docs/logo300.png" alt="Git Relay Logo" width="300">
</p>

# Git Relay

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)

A tool to synchronize git repos with smart scheduling and systemd integration.

Git Relay provides both a command-line interface and an interactive shell interface for managing your git repository synchronization.

## Features

- **Hub-based Synchronization:** Create "Hubs" to periodically sync commits between repos on same machine.
- **Local & Remote Support:** Sync local hubs to remote hubs over SSH.
- **Smart Scanning:** Automatically discovers repos in configured directories.
- **Systemd Integration:** Runs sync daemon as systemd service.
- **Interactive Shell:** A dedicated shell interface for quick management.

## Installation

```bash
# Clone the repository
git clone https://github.com/luismsgomes/gitrelay.git
cd gitrelay

# Install in editable mode
pip install -e .
```

## Quick Start

*Note: Git Relay is currently in active early development. Usage examples and documentation will be expanded as the CLI matures.*

## Concepts and Terminology

<details>
<summary>Click to expand details about Hubs, Discovery, and Naming Rules</summary>

### Hub
A **Hub** is a bare git repository managed exclusively by `gitrelay`. It acts as the central synchronization point for one or more **Local Repos** and potentially other **Remote Hubs** on different hosts.

- **Local Hub:** A hub located on the local machine, within the configured `hub_dir` (default: `~/githubs`).
- **Remote Hub:** A hub located on a remote host, accessed via SSH. Remote hubs are resolved by checking `~/.config/gitrelay/local.toml` on the remote host; if missing, Git Relay falls back to the `hub_dir` path configured for the local host.
- **Hub Name:** Hubs are identified by their relative path from the base `hub_dir`.
- **Hub Namespaces:** Hubs can be organized into subdirectories within the `hub_dir`, up to a configurable maximum depth. Thus a Hub Name may consist of several path components, separated with `/`. The namespace of a hub is thus the path up to and excluding the last path component of a hub name.
     - *Example:* hub name=`work/foo-bar` -> hub namespace=`work`.

#### Discovery and Location
- **Scanning:** `gitrelay` periodically scans configured hosts for hubs (including the local machine) for hubs -- hubs are just bare git repositories within a special dir and thus may be created without using `gitrelay`. Newly discovered hubs and missing hubs are reported in `~/.cache/scan/log.jsonl`. At any point in time, all local hubs that are known to `gitrelay` are listed in `~/.cache/scan/hubs/local.jsonl` and all remote hubs are listed on files named according to the remote host where the hubs were found: `~/.cache/scan/hubs/remote-{host_name}.jsonl`.

- **Hub Path:** A hub's path is `hub_dir` + `Hub Name` + `.git`.
     - *Example:* `work/foo-bar` -> `~/gitrepos/work/foo-bar.git`.

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

## License

This project is licensed under the GNU General Public License v3 (GPLv3) - see the [LICENSE](LICENSE) file for details.
