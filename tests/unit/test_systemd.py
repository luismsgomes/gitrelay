import json
import os
import stat

import pytest

from gitrelay.systemd import enable_service, get_service_status, start_service


@pytest.fixture
def fake_systemctl(tmp_path, monkeypatch):
    """
    Creates a fake 'systemctl' executable and adds it to PATH.
    It records every call (arguments) into a JSON file for inspection.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    record_file = tmp_path / "calls.jsonl"
    fake_exe = bin_dir / "systemctl"

    # The fake executable writes its own arguments to a JSONL file
    script_content = f"""#!/usr/bin/env python3
import sys
import json
with open('{record_file}', 'a') as f:
    f.write(json.dumps(sys.argv) + '\\n')
"""
    fake_exe.write_text(script_content)
    fake_exe.chmod(fake_exe.stat().st_mode | stat.S_IEXEC)

    # Inject our fake bin dir at the start of PATH
    monkeypatch.setenv("PATH", str(bin_dir), prepend=os.pathsep)

    return record_file


def test_enable_service_now_argument_separation(fake_systemctl):
    """
    Exposes the bug where 'enable --now' was passed as a single argument.
    """
    enable_service(now=True)

    # Read the recorded call
    calls = [json.loads(line) for line in fake_systemctl.read_text().splitlines()]
    assert len(calls) == 1

    cmd_args = calls[0]
    # cmd_args[0] is the path to fake systemctl
    # We expect: ['systemctl', '--user', 'enable', '--now', 'gitrelay.service']

    assert "enable" in cmd_args
    assert "--now" in cmd_args
    # This was the bug: it should NOT be combined
    assert "enable --now" not in cmd_args


def test_start_service_arguments(fake_systemctl):
    """Verifies basic start command structure."""
    start_service()

    calls = [json.loads(line) for line in fake_systemctl.read_text().splitlines()]
    cmd_args = calls[0]

    assert cmd_args[1] == "--user"
    assert cmd_args[2] == "start"
    assert cmd_args[3] == "gitrelay.service"


def test_get_service_status_no_crash(fake_systemctl):
    """Verifies that status command is called correctly."""
    get_service_status()

    calls = [json.loads(line) for line in fake_systemctl.read_text().splitlines()]
    assert any("status" in call for call in calls)
