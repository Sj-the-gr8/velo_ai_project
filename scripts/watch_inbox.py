"""Keep Velo running: check Gmail every POLL_INTERVAL_SECONDS and process new mail as it arrives.

    python scripts/watch_inbox.py

Each check is one incremental pipeline run (the cursor means only new mail is read), so new
receipts are extracted, stored, evaluated, and, if they raise an alert, notified within about
one interval. Temporary network, Gmail, or Gemini errors are logged and retried on the next
check. Stop with Ctrl+C.
"""
from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    # Allow `python scripts/watch_inbox.py` from the project root.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError

from config import settings
from scripts import run_pipeline_once

logger = logging.getLogger(__name__)

# Failures worth retrying on the next check. Anything else (for example a revoked token) stops the watcher.
TRANSIENT_ERRORS = (HttpError, TransportError, GoogleAPIError, OSError)


def watch(interval: float, max_checks: int | None = None, run: Callable[..., list] = run_pipeline_once.run,
          sleep: Callable[[float], None] = time.sleep) -> None:
    checks = 0
    while max_checks is None or checks < max_checks:
        checks += 1
        try:
            run(quiet=True)
        except TRANSIENT_ERRORS as error:
            logger.warning("Check failed, retrying in %.0fs: %s", interval, error)
        if max_checks is None or checks < max_checks:
            sleep(interval)


def main() -> None:
    # Currency symbols must not crash a legacy-codepage Windows console.
    sys.stdout.reconfigure(errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    print(f"{datetime.now():%H:%M:%S} Watching the inbox every {settings.poll_interval_seconds:.0f}s. Press Ctrl+C to stop.")
    try:
        watch(settings.poll_interval_seconds)
    except KeyboardInterrupt:
        print("Stopped watching.")


if __name__ == "__main__":
    main()
