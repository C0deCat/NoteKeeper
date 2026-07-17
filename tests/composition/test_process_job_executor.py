import subprocess
import sys

import psutil

from notekeeper.composition.process_job_executor import (
    _terminate_process_tree,
)


def test_terminate_process_tree_stops_parent_and_child() -> None:
    script = (
        "import subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "print(child.pid, flush=True); time.sleep(60)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert parent.stdout is not None
    child_pid = int(parent.stdout.readline().strip())
    try:
        _terminate_process_tree(parent.pid)
        parent.wait(timeout=5)
        assert not psutil.pid_exists(parent.pid)
        assert not psutil.pid_exists(child_pid)
    finally:
        for pid in (child_pid, parent.pid):
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass
