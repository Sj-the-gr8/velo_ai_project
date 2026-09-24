from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import settings
from db.db import Database
from extraction.llm_extractor import extract_billing_event
from ingestion.gmail_client import GmailClient
from notify.notifier import notify_alert
from rules.trigger_engine import BillingRecord, evaluate_subscription


def start_review_agent() -> None:
    """Start the sandbox agent only after the user clicks the notification."""
    from agent.vision_agent import run_agent

    run_agent()


def run() -> None:
    database = Database(settings.database_path)
    database.migrate()
    client = GmailClient(settings.gmail_credentials_file, 
                         settings.gmail_token_file, 
                         settings.gmail_user, 
                         settings.gmail_cursor_file)
    since = None if settings.gmail_cursor_file.exists() else datetime.now(timezone.utc) - timedelta(days=settings.gmail_lookback_days)
    messages = client.fetch_billing_emails(since=since)
    for message in messages:
        event = extract_billing_event(message["body"])
        if event is None:
            continue
        with database.connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO subscriptions (merchant_name, canonical_id, first_seen, last_seen, current_amount, currency) VALUES (?, ?, ?, ?, ?, ?)",
                (event.merchant.name, event.merchant.canonical_id, event.billing_date.isoformat(), event.billing_date.isoformat(), float(event.amount), event.currency),
            )
            connection.execute(
                "UPDATE subscriptions SET last_seen = ?, current_amount = ?, currency = ? WHERE canonical_id = ?",
                (event.billing_date.isoformat(), float(event.amount), event.currency, event.merchant.canonical_id),
            )
            subscription = connection.execute("SELECT id FROM subscriptions WHERE canonical_id = ?", (event.merchant.canonical_id,)).fetchone()
            connection.execute(
                "INSERT OR IGNORE INTO billing_events (subscription_id, amount, currency, message_id, received_date, billing_date, raw_snippet) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (subscription["id"], float(event.amount), event.currency, message["message_id"], message["received_date"], event.billing_date.isoformat(), event.raw_text[:2000]),
            )
        with database.connection() as connection:
            rows = connection.execute("SELECT * FROM billing_events WHERE subscription_id = ? ORDER BY billing_date", (subscription["id"],)).fetchall()
        history = [
            BillingRecord(
                str(subscription["id"]),
                row["amount"],
                datetime.fromisoformat(row["billing_date"]),
                row["raw_snippet"],
            )
            for row in rows
        ]
        alert = evaluate_subscription(history)
        if alert:
            with database.connection() as connection:
                existing_alert = connection.execute(
                    "SELECT 1 FROM alerts WHERE subscription_id = ? AND reason = ? AND resolved = 0",
                    (subscription["id"], alert.reason.value),
                ).fetchone()
                if existing_alert is None:
                    connection.execute(
                        "INSERT INTO alerts (subscription_id, reason, created_at) VALUES (?, ?, datetime('now'))",
                        (subscription["id"], alert.reason.value),
                    )
                    notify_alert(event.merchant.name, alert, start_review_agent)


if __name__ == "__main__":
    run()
