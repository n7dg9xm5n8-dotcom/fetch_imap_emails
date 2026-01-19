from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class FetchImapEmailsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        import imaplib
        import email
        from email.header import decode_header
        result_list = []
        try:
            # Provider-level defaults (configured via "Authorize / Configure")
            creds = getattr(self.runtime, "credentials", {}) or {}

            # Per-node overrides (tool parameters) take precedence when provided
            config_name = tool_parameters.get("config_name") or creds.get("config_name")
            account = tool_parameters.get("email_account") or creds.get("email_account")
            password = tool_parameters.get("email_password") or creds.get("email_password")
            server = tool_parameters.get("imap_server") or creds.get("imap_server")
            port = tool_parameters.get("imap_port") or creds.get("imap_port")
            recent_count = tool_parameters.get("recent_count") or creds.get("recent_count") or 5

            # Normalize types
            port = int(port)
            recent_count = int(recent_count)

            # Basic validation (so node-level overrides still safe)
            if not account or "@" not in str(account):
                raise ValueError("Invalid or missing email_account")
            if not password:
                raise ValueError("Missing email_password")
            if not server:
                raise ValueError("Missing imap_server")
            if port <= 0:
                raise ValueError("imap_port must be a positive integer")
            if recent_count <= 0:
                raise ValueError("recent_count must be a positive integer")
            # 连接IMAP服务器
            mail = imaplib.IMAP4_SSL(server, port)
            mail.login(account, password)
            mail.select("inbox")
            typ, data = mail.search(None, "ALL")
            mail_ids = data[0].split()
            # 获取最近N封邮件
            for i in mail_ids[-recent_count:][::-1]:
                typ, msg_data = mail.fetch(i, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg.get("Subject"))[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")
                        from_ = msg.get("From")
                        date_ = msg.get("Date")
                        # 获取正文摘要
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain" and part.get("Content-Disposition") is None:
                                    charset = part.get_content_charset() or "utf-8"
                                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                                    break
                        else:
                            charset = msg.get_content_charset() or "utf-8"
                            body = msg.get_payload(decode=True).decode(charset, errors="ignore")
                        result_list.append({
                            "subject": subject,
                            "from": from_,
                            "date": date_,
                            "body": body
                        })
            mail.logout()
            yield self.create_json_message({
                "config_name": config_name,
                "email_account": account,
                "imap_server": server,
                "imap_port": port,
                "recent_count": recent_count,
                "emails": result_list,
            })
        except Exception as e:
            yield self.create_json_message({"error": str(e)})
