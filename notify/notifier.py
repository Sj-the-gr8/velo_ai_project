from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

from desktop_notifier import DesktopNotifier, Urgency

from rules.trigger_engine import Alert


def _message(merchant_name: str, alert: Alert) -> str:
    return f"{merchant_name} needs review: {alert.reason.value.replace('_', ' ')}."


def notify_alerts(alerts: Sequence[tuple[str, Alert]], on_review: Callable[[str, Alert], None], timeout: float = 120) -> bool:
    """Show one notification per alert and wait up to ``timeout`` seconds for a click.

    ``on_review`` runs only for an explicitly clicked notification, and only after the
    event loop has exited, so it may use blocking APIs such as Playwright's sync API.
    Returns whether a notification was clicked.
    """
    if not alerts:
        return False
    clicked: list[tuple[str, Alert]] = []

    async def send_and_wait() -> None:
        notifier = DesktopNotifier(app_name="Velo")
        click = asyncio.Event()

        def handler(merchant_name: str, alert: Alert) -> Callable[[], None]:
            def on_clicked() -> None:
                if not clicked:
                    clicked.append((merchant_name, alert))
                click.set()
            return on_clicked

        for merchant_name, alert in alerts:
            await notifier.send(
                title="Velo subscription alert",
                message=_message(merchant_name, alert),
                urgency=Urgency.Normal,
                on_clicked=handler(merchant_name, alert),
            )
        try:
            await asyncio.wait_for(click.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    asyncio.run(send_and_wait())
    if clicked:
        on_review(*clicked[0])
        return True
    return False


def notify_alert(merchant_name: str, alert: Alert, on_review: Callable[[], None], timeout: float = 120) -> bool:
    return notify_alerts([(merchant_name, alert)], lambda _merchant, _alert: on_review(), timeout)
