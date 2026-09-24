import sqlite3
from datetime import date
from decimal import Decimal

from extraction.schema import BillingEvent, Merchant
from scripts import run_pipeline_once


class FakeGmail:
    def __init__(self, messages):
        self.messages = messages
        self.cursor = None

    def fetch_billing_emails(self, since=None):
        return [m for m in sorted(self.messages, key=lambda m: m["internal_date"]) if self.cursor is None or m["internal_date"] > self.cursor]

    def save_cursor(self, internal_date):
        self.cursor = internal_date


def message(message_id, internal_date, body):
    return {"message_id": message_id, "internal_date": internal_date, "received_date": "2026-01-01T00:00:00+00:00", "body": body}


def fake_extractor(body, message_id=None):
    # body format: "merchant|amount|YYYY-MM-DD", or "junk" for a non-billing email
    if body == "junk":
        return None
    merchant, amount, billing_date = body.split("|")
    return BillingEvent(merchant=Merchant(name=merchant, canonical_id=merchant), amount=Decimal(amount), currency="USD",
                        billing_date=date.fromisoformat(billing_date), confidence=0.9, raw_text=body)


def rows(path, query):
    with sqlite3.connect(path) as connection:
        return connection.execute(query).fetchall()


def test_pipeline_stores_events_raises_alert_and_is_idempotent(test_settings):
    gmail = FakeGmail([
        message("m3", 3, "Acme|12.99|2026-03-01"),
        message("m1", 1, "Acme|9.99|2026-01-01"),
        message("m2", 2, "Acme|9.99|2026-01-31"),
        message("m4", 4, "junk"),
        message("m5", 5, "Other|5.00|2026-03-01"),
    ])
    alerts = run_pipeline_once.run(client=gmail, extractor=fake_extractor, notify=False)

    assert [(name, alert.reason.value) for name, alert in alerts] == [("Acme", "price_hike")]
    assert gmail.cursor == 5
    db = test_settings.database_path
    assert rows(db, "SELECT merchant_name, current_amount, first_seen, last_seen FROM subscriptions ORDER BY merchant_name") == [
        ("Acme", 12.99, "2026-01-01", "2026-03-01"), ("Other", 5.0, "2026-03-01", "2026-03-01")]
    assert rows(db, "SELECT COUNT(*) FROM billing_events") == [(4,)]
    assert rows(db, "SELECT reason FROM alerts") == [("price_hike",)]

    # A second run over the same mail (cursor reset) must not duplicate rows or alerts.
    gmail.cursor = None
    assert run_pipeline_once.run(client=gmail, extractor=fake_extractor, notify=False) == []
    assert rows(db, "SELECT COUNT(*) FROM billing_events") == [(4,)]
    assert rows(db, "SELECT COUNT(*) FROM alerts") == [(1,)]


def test_older_mail_does_not_overwrite_current_amount(test_settings):
    newest_first = FakeGmail([])
    newest_first.fetch_billing_emails = lambda since=None: [message("b", 2, "Acme|12.99|2026-02-01"), message("a", 1, "Acme|9.99|2026-01-01")]
    run_pipeline_once.run(client=newest_first, extractor=fake_extractor, notify=False)
    assert rows(test_settings.database_path, "SELECT current_amount, first_seen, last_seen FROM subscriptions") == [(12.99, "2026-01-01", "2026-02-01")]


def test_notification_click_hands_off_to_agent(test_settings, monkeypatch):
    calls = []
    monkeypatch.setattr(run_pipeline_once, "notify_alerts", lambda alerts, on_review, timeout: on_review(*alerts[0]) or True)
    monkeypatch.setattr(run_pipeline_once, "start_review_agent", lambda merchant, alert: calls.append((merchant, alert.reason.value)))
    gmail = FakeGmail([message("m1", 1, "Acme|9.99|2026-01-01"), message("m2", 2, "Acme|19.99|2026-01-31")])
    run_pipeline_once.run(client=gmail, extractor=fake_extractor)
    assert calls == [("Acme", "price_hike")]
