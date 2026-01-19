from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, Iterable

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

import email
import imaplib
from email.header import decode_header, make_header


@dataclass(frozen=True)
class ImapConfig:
    config_name: str | None
    email_account: str
    email_password: str
    imap_server: str
    imap_port: int
    recent_count: int


TRASH_FOLDERS = (
    "Trash",
    "Deleted Items",
    "Deleted Messages",
    "垃圾箱",
    "回收站",
    "Bin",
    "[Gmail]/Trash",
)


class FetchImapEmailsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            config = self._build_config(tool_parameters)
            emails, deleted_count, trash_empty = self._fetch_and_delete_emails(config)
            yield self.create_json_message(
                {
                    "config_name": config.config_name,
                    "email_account": config.email_account,
                    "imap_server": config.imap_server,
                    "imap_port": config.imap_port,
                    "recent_count": config.recent_count,
                    "emails": emails,
                    "deleted_count": deleted_count,
                    "trash_cleared": trash_empty,
                }
            )
        except Exception as exc:
            yield self.create_json_message({"error": str(exc)})

    def _build_config(self, tool_parameters: dict[str, Any]) -> ImapConfig:
        creds = getattr(self.runtime, "credentials", {}) or {}
        config_name = tool_parameters.get("config_name") or creds.get("config_name")
        account = tool_parameters.get("email_account") or creds.get("email_account")
        password = tool_parameters.get("email_password") or creds.get("email_password")
        server = tool_parameters.get("imap_server") or creds.get("imap_server")
        port = tool_parameters.get("imap_port") or creds.get("imap_port")
        recent_count = tool_parameters.get("recent_count") or creds.get("recent_count") or 5

        if not account or "@" not in str(account):
            raise ValueError("Invalid or missing email_account")
        if not password:
            raise ValueError("Missing email_password")
        if not server:
            raise ValueError("Missing imap_server")

        try:
            port = int(port)
        except Exception as exc:
            raise ValueError("imap_port must be a positive integer") from exc
        if port <= 0:
            raise ValueError("imap_port must be a positive integer")

        try:
            recent_count = int(recent_count)
        except Exception as exc:
            raise ValueError("recent_count must be a positive integer") from exc
        if recent_count <= 0:
            raise ValueError("recent_count must be a positive integer")

        return ImapConfig(
            config_name=str(config_name) if config_name else None,
            email_account=str(account),
            email_password=str(password),
            imap_server=str(server),
            imap_port=port,
            recent_count=recent_count,
        )

    def _fetch_and_delete_emails(self, config: ImapConfig) -> tuple[list[dict[str, Any]], int, bool]:
        mail = imaplib.IMAP4_SSL(config.imap_server, config.imap_port)
        deleted_count = 0
        emails: list[dict[str, Any]] = []
        trash_cleared = False
        try:
            mail.login(config.email_account, config.email_password)
            mail.select("INBOX")
            _, data = mail.search(None, "ALL")
            if not data or data[0] is None:
                mail_ids = []
            else:
                mail_ids = data[0].split()
            target_ids = list(reversed(mail_ids[-config.recent_count :]))

            for mail_id in target_ids:
                _, msg_data = mail.fetch(mail_id, "(RFC822)")
                for response_part in msg_data:
                    if not isinstance(response_part, tuple):
                        continue
                    msg = email.message_from_bytes(response_part[1])
                    emails.append(self._extract_email(msg))
                mail.store(mail_id, "+FLAGS", "\\Deleted")
                deleted_count += 1

            if target_ids:
                mail.expunge()
            trash_cleared = self._empty_trash(mail)
        finally:
            mail.logout()

        return emails, deleted_count, trash_cleared

    def _extract_email(self, msg: email.message.Message) -> dict[str, Any]:
        subject = self._decode_header_value(msg.get("Subject"))
        from_ = self._decode_header_value(msg.get("From"))
        date_ = msg.get("Date")
        body = self._extract_body(msg)
        return {"subject": subject, "from": from_, "date": date_, "body": body}

    def _decode_header_value(self, value: str | None) -> str:
        if not value:
            return ""
        decoded = decode_header(value)
        return str(make_header(decoded))

    def _extract_body(self, msg: email.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and part.get("Content-Disposition") is None:
                    return self._decode_part(part)
            for part in msg.walk():
                if part.get_content_type() == "text/html" and part.get("Content-Disposition") is None:
                    return self._decode_part(part)
            return ""
        return self._decode_part(msg)

    def _decode_part(self, part: email.message.Message) -> str:
        charset = part.get_content_charset() or "utf-8"
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        return payload.decode(charset, errors="ignore")

    def _empty_trash(self, mail: imaplib.IMAP4_SSL) -> bool:
        _, mailboxes = mail.list()
        trash_folder = self._find_trash_folder(mailboxes)
        if not trash_folder:
            return False
        mail.select(trash_folder)
        mail.store("1:*", "+FLAGS", "\\Deleted")
        mail.expunge()
        return True

    def _find_trash_folder(self, mailboxes: Iterable[bytes] | None) -> str | None:
        if not mailboxes:
            return None
        for line in mailboxes:
            try:
                mailbox = line.decode("utf-8", errors="ignore")
            except Exception:
                continue
            mailbox_name = self._parse_mailbox_name(mailbox)
            if not mailbox_name:
                continue
            for folder in TRASH_FOLDERS:
                if mailbox_name.lower() == folder.lower():
                    return mailbox_name
        return None

    def _parse_mailbox_name(self, mailbox_line: str) -> str | None:
        if "\"" in mailbox_line:
            parts = mailbox_line.split("\"")
            if len(parts) >= 2:
                return parts[-2]
        tokens = mailbox_line.split()
        if tokens:
            return tokens[-1].strip("\"")
        return None
