from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from desktop_notifier import Button, DesktopNotifier, Urgency

from rules.trigger_engine import Alert, AlertReason, BillingRecord

TITLES = {
    AlertReason.PRICE_HIKE: "price went up",
    AlertReason.DORMANT: "possibly unused",
    AlertReason.TRIAL_CONVERT: "free trial is now paid",
}
SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
MONTHLY_DAYS = 30


@dataclass(frozen=True)
class AlertNotice:
    merchant_name: str
    alert: Alert
    details: str


def _money(amount: float, currency: str) -> str:
    symbol = SYMBOLS.get(currency.upper())
    return f"{symbol}{amount:,.2f}" if symbol else f"{amount:,.2f} {currency.upper()}"


def _day(value) -> str:
    return f"{value.day} {value:%b %Y}"


def describe_alert(alert: Alert, history: Sequence[BillingRecord], currency: str = "USD") -> str:
    """Summarise the facts behind an alert so the user can decide from the notification alone."""
    ordered = sorted(history, key=lambda record: record.billing_date)
    latest = ordered[-1]
    next_charge = f"Next charge about {_day(latest.billing_date + timedelta(days=MONTHLY_DAYS))}."
    yearly = _money(latest.amount * 12, currency)
    if alert.reason is AlertReason.PRICE_HIKE:
        previous = ordered[-2].amount
        change = (latest.amount - previous) / previous * 100
        return (f"{_money(previous, currency)} to {_money(latest.amount, currency)} a month (+{change:.0f}%), "
                f"now {yearly} a year. {next_charge}")
    if alert.reason is AlertReason.DORMANT:
        total = _money(sum(record.amount for record in ordered), currency)
        return (f"{_money(latest.amount, currency)} a month for {len(ordered)} months with no sign of use "
                f"({total} so far). {next_charge}")
    return (f"Trial ended: charged {_money(latest.amount, currency)} on {_day(latest.billing_date)}, "
            f"{yearly} a year if kept. {next_charge}")


def notify_alerts(notices: Sequence[AlertNotice], on_cancel: Callable[[AlertNotice], None], timeout: float = 120) -> AlertNotice | None:
    """Show one notification per alert with "Cancel subscription" and "Do nothing" buttons.

    Waits up to ``timeout`` seconds, or until every notice has an answer. ``on_cancel`` runs only
    when the user presses "Cancel subscription", and only after the event loop has exited, so it
    may use blocking APIs such as Playwright's sync API. Returns the notice chosen for cancellation.
    """
    if not notices:
        return None
    chosen: list[AlertNotice] = []

    async def send_and_wait() -> None:
        notifier = DesktopNotifier(app_name="Velo")
        finished = asyncio.Event()
        answered: set[int] = set()

        def answer(index: int, cancel: bool) -> Callable[[], None]:
            def pressed() -> None:
                answered.add(index)
                if cancel and not chosen:
                    chosen.append(notices[index])
                if chosen or len(answered) == len(notices):
                    finished.set()
            return pressed

        for index, notice in enumerate(notices):
            await notifier.send(
                title=f"{notice.merchant_name}: {TITLES[notice.alert.reason]}",
                message=notice.details,
                urgency=Urgency.Normal,
                buttons=(Button("Cancel subscription", on_pressed=answer(index, cancel=True)),
                         Button("Do nothing", on_pressed=answer(index, cancel=False))),
            )
        try:
            await asyncio.wait_for(finished.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    asyncio.run(send_and_wait())
    if chosen:
        on_cancel(chosen[0])
        return chosen[0]
    return None
