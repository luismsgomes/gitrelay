import sys
from unittest.mock import patch

# This is a permanent testing asset.
# It wraps the real gitrelay.main but mocks the daemon loop
# to allow for deterministic end-to-end integration testing.


def mock_daemon_loop():
    import signal
    import time

    def handle_term(signum, frame):
        # Log a specific token so the test knows we received the signal
        # Use stderr to ensure it hits the journal immediately
        print("MOCK_DAEMON_STOPPED", file=sys.stderr)
        sys.stderr.flush()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_term)

    # Use stderr for all tokens to ensure consistency in journal logs
    print("MOCK_DAEMON_STARTING", file=sys.stderr)
    sys.stderr.flush()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    # We must import inside __main__ to avoid issues during patching
    import gitrelay.main

    # We patch get_executable_path so that when 'daemon install' is run,
    # it uses THIS script path for the systemd unit file.
    with patch("gitrelay.main.get_executable_path", return_value=__file__):
        # We patch the actual loop function right before main() runs
        with patch("gitrelay.main.daemon.daemon_start", side_effect=mock_daemon_loop):
            gitrelay.main.main()
