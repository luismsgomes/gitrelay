# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import subprocess
from enum import Enum
from pathlib import Path
from typing import List


class GitHookType(str, Enum):
    """Supported Git hook names."""

    POST_RECEIVE = "post-receive"
    POST_COMMIT = "post-commit"
    POST_UPDATE = "post-update"
    PRE_PUSH = "pre-push"


def install_git_alias() -> None:
    """Installs a global git alias 'relay' that calls 'gitrelay'."""
    subprocess.run(["git", "config", "--global", "alias.relay", "gitrelay"], check=True)


def is_bare_repository(path: Path) -> bool:
    """Checks if a directory is a bare git repository."""
    try:
        res = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-bare-repository"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def init_repository(path: Path) -> None:
    """
    Initializes a new git repository at the specified path.
    If the path ends with .git (case-insensitive), it initializes a bare repository.
    Raises FileExistsError if path already exists.
    """
    if path.exists():
        raise FileExistsError(f"Path already exists: {path}")

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "init"]
    if path.name.lower().endswith(".git"):
        cmd.append("--bare")
    cmd.append(str(path))

    subprocess.run(cmd, check=True)


def install_hook(
    repo_path: Path, hook_type: GitHookType, relay_args: List[str]
) -> None:
    """
    Installs a git hook in a specified git repo (bare or non-bare).
    The hook calls 'gitrelay' with the provided arguments using 'exec'.
    """
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    if is_bare_repository(repo_path):
        hooks_dir = repo_path / "hooks"
    else:
        hooks_dir = repo_path / ".git" / "hooks"

    if not hooks_dir.exists():
        if not (repo_path / ".git").exists() and not is_bare_repository(repo_path):
            raise ValueError(f"Not a git repository: {repo_path}")
        hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_path = hooks_dir / hook_type.value
    args_str = " ".join(relay_args)
    hook_content = (
        "#!/bin/sh\n"
        'if [ "$GITRELAY_HOOK_WAIT" = "false" ]; then\n'
        f"    gitrelay {args_str} &\n"
        "else\n"
        f"    exec gitrelay {args_str}\n"
        "fi\n"
    )

    with open(hook_path, "w") as f:
        f.write(hook_content)

    hook_path.chmod(0o755)
