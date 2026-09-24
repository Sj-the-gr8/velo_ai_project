from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def mock_site_running(url: str | None = None) -> bool:
    try:
        with urllib.request.urlopen(url or settings.mock_site_url, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


@contextmanager
def mock_site(url: str | None = None, startup_timeout: float = 15):
    """Use the local mock site, starting it for the duration of the block if it is not already up."""
    url = url or settings.mock_site_url
    if mock_site_running(url):
        yield
        return
    process = subprocess.Popen([sys.executable, "-m", "agent.mock_site.app"], cwd=PROJECT_ROOT)
    try:
        deadline = time.monotonic() + startup_timeout
        while not mock_site_running(url):
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"Mock site did not start at {url}")
            time.sleep(0.2)
        yield
    finally:
        process.terminate()
        process.wait(timeout=10)
