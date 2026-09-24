from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __package__ in (None, ""):
    # Allow `python scripts/run_pipeline_once.py` from the project root.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from db.db import Database
from extraction.llm_extractor import extract_billing_event
from extraction.schema import BillingEvent
from ingestion.gmail_client import GmailClient
from notify.notifier import notify_alerts
from rules.trigger_engine import Alert, BillingRecord, evaluate_subscription

logger = logging.getLogger(__name__)


def start_review_agent(merchant_name: str, alert: Alert) -> None:
    """Start the sandbox agent only after the user clicks the notification."""
    from agent.sandbox import mock_site
    from agent.vision_agent import run_agent

    with mock_site():
        run_id = run_agent()
    print(f"Sandbox agent run {run_id} finished for {merchant_name} ({alert.reason.value}); see agent_actions.")


def _store_event(database: Database, message: dict, event: BillingEvent) -> int:
    billing_date = event.billing_date.isoformat()
    with database.connection() as connection:
        # Messages can arrive out of order, so only the newest charge sets the current amount.
        connection.execute(
            """INSERT INTO subscriptions (merchant_name, canonical_id, first_seen, last_seen, current_amount, currency)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(canonical_id) DO UPDATE SET
                   first_seen = MIN(first_seen, excluded.first_seen),
                   current_amount = CASE WHEN excluded.last_seen >= last_seen THEN excluded.current_amount ELSE current_amount END,
                   currency = CASE WHEN excluded.last_seen >= last_seen THEN excluded.currency ELSE currency END,
                   last_seen = MAX(last_seen, excluded.last_seen)""",
            (event.merchant.name, event.merchant.canonical_id, billing_date, billing_date, float(event.amount), event.currency),
        )
        subscription = connection.execute("SELECT id FROM subscriptions WHERE canonical_id = ?", (event.merchant.canonical_id,)).fetchone()
        connection.execute(
            "INSERT OR IGNORE INTO billing_events (subscription_id, amount, currency, message_id, received_date, billing_date, raw_snippet) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (subscription["id"], float(event.amount), event.currency, message["message_id"], message["received_date"], billing_date, event.raw_text[:2000]),
        )
    return subscription["id"]


def _evaluate_and_record(database: Database, subscription_id: int) -> tuple[str, Alert] | None:
    """Run the rules over the full history and save a new alert unless the same one is already open."""
    with database.connection() as connection:
        merchant_name = connection.execute("SELECT merchant_name FROM subscriptions WHERE id = ?", (subscription_id,)).fetchone()["merchant_name"]
        rows = connection.execute("SELECT * FROM billing_events WHERE subscription_id = ? ORDER BY billing_date", (subscription_id,)).fetchall()
        history = [BillingRecord(str(subscription_id), row["amount"], datetime.fromisoformat(row["billing_date"]), row["raw_snippet"]) for row in rows]
        alert = evaluate_subscription(history)
        if alert is None:
            return None
        existing_alert = connection.execute(
            "SELECT 1 FROM alerts WHERE subscription_id = ? AND reason = ? AND resolved = 0",
            (subscription_id, alert.reason.value),
        ).fetchone()
        if existing_alert is not None:
            return None
        connection.execute(
            "INSERT INTO alerts (subscription_id, reason, created_at) VALUES (?, ?, datetime('now'))",
            (subscription_id, alert.reason.value),
        )
    return merchant_name, alert


def run(client: GmailClient | None = None, extractor=extract_billing_event, notify: bool = True) -> list[tuple[str, Alert]]:
    database = Database(settings.database_path)
    database.migrate()
    client = client or GmailClient(settings.gmail_credentials_file,
                                   settings.gmail_token_file,
                                   settings.gmail_user,
                                   settings.gmail_cursor_file)
    since = None if settings.gmail_cursor_file.exists() else datetime.now(timezone.utc) - timedelta(days=settings.gmail_lookback_days)
    messages = client.fetch_billing_emails(since=since)

    affected: set[int] = set()
    stored = skipped = 0
    for message in messages:
        with database.connection() as connection:
            seen = connection.execute("SELECT 1 FROM billing_events WHERE message_id = ?", (message["message_id"],)).fetchone()
        if seen is None:
            event = extractor(message["body"], message_id=message["message_id"])
            if event is None:
                skipped += 1
            else:
                affected.add(_store_event(database, message, event))
                stored += 1
        # Advance only after the message is handled, so a crash re-fetches it next run.
        client.save_cursor(message["internal_date"])

    new_alerts = [result for subscription_id in sorted(affected) if (result := _evaluate_and_record(database, subscription_id))]
    print(f"Fetched {len(messages)} messages: {stored} billing events stored, {skipped} skipped, {len(new_alerts)} new alerts.")

    # Alerts are committed before any notification, so the agent can write to the database.
    if notify and new_alerts:
        print(f"Waiting up to {settings.notify_click_timeout:.0f}s for a notification click...")
        if not notify_alerts(new_alerts, start_review_agent, timeout=settings.notify_click_timeout):
            print("No notification was clicked; the agent was not started.")
    return new_alerts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
