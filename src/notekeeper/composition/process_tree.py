"""Operating-system process-tree termination."""

import psutil


def terminate_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    descendants = parent.children(recursive=True)
    _terminate(parent)
    for process in descendants:
        _terminate(process)

    _, alive = psutil.wait_procs(descendants, timeout=3)
    for process in alive:
        _kill(process)

    try:
        parent.wait(timeout=3)
    except psutil.NoSuchProcess:
        return
    except psutil.TimeoutExpired:
        _kill(parent)


def _terminate(process: psutil.Process) -> None:
    try:
        process.terminate()
    except psutil.NoSuchProcess:
        pass


def _kill(process: psutil.Process) -> None:
    try:
        process.kill()
    except psutil.NoSuchProcess:
        pass


__all__ = ["terminate_process_tree"]
