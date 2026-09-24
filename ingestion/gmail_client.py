from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ingestion.email_parser import extract_plain_text

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    def __init__(self, credentials_file: Path, token_file: Path, user: str = "me", cursor_file: Path | None = None):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.user = user
        self.cursor_file = cursor_file

    def _service(self):
        credentials = Credentials.from_authorized_user_file(self.token_file, SCOPES) if self.token_file.exists() else None
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
            credentials = flow.run_local_server(port=0)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=credentials)

    def fetch_billing_emails(self, since: datetime | None = None) -> list[dict]:
        if since is None and self.cursor_file and self.cursor_file.exists():
            since = datetime.fromtimestamp(float(self.cursor_file.read_text(encoding="utf-8")), timezone.utc)
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        query = f"after:{int(since.timestamp())} (receipt OR invoice OR subscription OR trial)"
        service = self._service()
        messages = []
        page_token = None
        while True:
            result = service.users().messages().list(userId=self.user, q=query, pageToken=page_token, maxResults=100).execute()
            for item in result.get("messages", []):
                raw = service.users().messages().get(userId=self.user, id=item["id"], format="raw").execute()
                message = BytesParser(policy=policy.default).parsebytes(__import__("base64").urlsafe_b64decode(raw["raw"]))
                messages.append({"message_id": item["id"], "received_date": message.get("Date", ""), "body": extract_plain_text(message)})
            page_token = result.get("nextPageToken")
            if not page_token:
                if self.cursor_file:
                    self.cursor_file.write_text(str(datetime.now(timezone.utc).timestamp()), encoding="utf-8")
                return messages
