from __future__ import annotations

import subprocess
import sys
import threading
import time

from app.runtime.shutdown import mark_shutting_down, reset_shutdown_state
from app.services.subprocess_runner import run_command, terminate_active_subprocesses


def test_terminate_active_subprocesses_kills_registered_command() -> None:
    reset_shutdown_state()
    errors: list[Exception] = []

    def worker() -> None:
        try:
            run_command([sys.executable, "-c", "import time; time.sleep(60)"])
        except Exception as exc:  # noqa: BLE001 - capture interruption
            errors.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    time.sleep(0.25)
    mark_shutting_down()
    terminate_active_subprocesses()
    thread.join(timeout=5)
    reset_shutdown_state()
    assert not thread.is_alive()
