import pytest
from google.auth.exceptions import TransportError

from scripts.watch_inbox import watch


def test_checks_repeatedly_and_sleeps_between_checks():
    calls, sleeps = [], []
    watch(60, max_checks=3, run=lambda quiet: calls.append(quiet) or [], sleep=sleeps.append)
    assert calls == [True, True, True]
    assert sleeps == [60, 60]


def test_transient_error_is_retried_on_next_check():
    outcomes = iter([TransportError("network down"), ConnectionError("reset"), None])
    calls = []

    def run(quiet):
        calls.append(quiet)
        outcome = next(outcomes)
        if outcome:
            raise outcome
        return []

    watch(1, max_checks=3, run=run, sleep=lambda _: None)
    assert len(calls) == 3


def test_unexpected_error_stops_the_watcher():
    def run(quiet):
        raise RuntimeError("token revoked")

    with pytest.raises(RuntimeError):
        watch(1, max_checks=3, run=run, sleep=lambda _: None)
