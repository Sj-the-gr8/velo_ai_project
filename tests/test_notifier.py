import notify.notifier as notifier
from rules.trigger_engine import Alert, AlertReason

ALERT = Alert(AlertReason.PRICE_HIKE, "1")


class FakeNotifier:
    click = False
    sent = []

    def __init__(self, app_name):
        pass

    async def send(self, title, message, urgency, on_clicked):
        FakeNotifier.sent.append(message)
        if FakeNotifier.click:
            on_clicked()


def test_click_runs_review_after_loop(monkeypatch):
    monkeypatch.setattr(notifier, "DesktopNotifier", FakeNotifier)
    FakeNotifier.click, FakeNotifier.sent = True, []
    reviewed = []
    assert notifier.notify_alerts([("Acme", ALERT)], lambda merchant, alert: reviewed.append(merchant), timeout=5)
    assert reviewed == ["Acme"]
    assert FakeNotifier.sent == ["Acme needs review: price hike."]


def test_no_click_never_starts_review(monkeypatch):
    monkeypatch.setattr(notifier, "DesktopNotifier", FakeNotifier)
    FakeNotifier.click, FakeNotifier.sent = False, []
    reviewed = []
    assert not notifier.notify_alerts([("Acme", ALERT)], lambda merchant, alert: reviewed.append(merchant), timeout=0.1)
    assert reviewed == []
