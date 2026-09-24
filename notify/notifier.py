from __future__ import annotations

import asyncio
from collections.abc import Callable

from desktop_notifier import DesktopNotifier, Notification

from rules.trigger_engine import Alert


def notify_alert(merchant_name: str, alert: Alert, on_review: Callable[[], None]) -> None:
    message = f"{merchant_name} needs review: {alert.reason.value.replace('_', ' ')}."
    notifier = DesktopNotifier()

    async def send() -> None:
        notification = Notification(title="Velo subscription alert", message=message, urgency="normal")
        await notifier.send(notification, on_click=lambda: on_review())

    asyncio.run(send())
