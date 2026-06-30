from __future__ import annotations

import subprocess
import threading

from app.runtime.shutdown import is_shutting_down

_registry_lock = threading.Lock()
_active_processes: set[subprocess.Popen[str]] = set()


class SubprocessInterruptedError(subprocess.SubprocessError):
    pass


def _register(process: subprocess.Popen[str]) -> None:
    with _registry_lock:
        _active_processes.add(process)


def _unregister(process: subprocess.Popen[str]) -> None:
    with _registry_lock:
        _active_processes.discard(process)


def terminate_active_subprocesses() -> None:
    with _registry_lock:
        processes = list(_active_processes)

    for process in processes:
        if process.poll() is not None:
            _unregister(process)
            continue
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        except OSError:
            pass
        finally:
            _unregister(process)


def run_command(
    command: list[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    if is_shutting_down():
        raise SubprocessInterruptedError("服务正在关闭，已取消外部命令。")

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _register(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(
            args=command,
            returncode=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=timeout or 0,
            output=stdout,
            stderr=stderr,
        ) from exc
    finally:
        _unregister(process)
