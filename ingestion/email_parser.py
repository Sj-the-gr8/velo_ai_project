from __future__ import annotations

from email.message import Message
from html import unescape
import re


def _strip_html(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_plain_text(message: Message) -> str:
    parts = message.walk() if message.is_multipart() else [message]
    plain = []
    html = []
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        content = part.get_payload(decode=True)
        if content is None:
            continue
        text = content.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/plain":
            plain.append(text)
        elif part.get_content_type() == "text/html":
            html.append(text)
    return "\n".join(plain).strip() or _strip_html("\n".join(html))
