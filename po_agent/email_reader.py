"""Turn a raw .eml file into plain text: headers, body and the text of any PDF attachment."""
import hashlib
import html
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from typing import List, Optional

from pypdf import PdfReader

from .config import MAX_PDF_PAGES


@dataclass
class Attachment:
    name: str
    text: str
    truncated: bool = False


@dataclass
class ParsedEmail:
    message_id: str
    sender_name: str
    sender_email: str
    subject: str
    date: Optional[datetime]
    body: str
    attachments: List[Attachment] = field(default_factory=list)


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>|</p>|</tr>|</div>", "\n", raw_html)
    text = re.sub(r"(?i)</td>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def pdf_to_text(data: bytes) -> Attachment:
    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[:MAX_PDF_PAGES]
    text = "\n".join(page.extract_text() or "" for page in pages)
    return Attachment(name="", text=text, truncated=len(reader.pages) > MAX_PDF_PAGES)


def parse_eml(raw: bytes) -> ParsedEmail:
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    sender_name, sender_email = parseaddr(msg.get("From", ""))
    try:
        date = parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
    except (TypeError, ValueError):
        date = None

    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = ""
    if body_part is not None:
        body = body_part.get_content()
        if body_part.get_content_type() == "text/html":
            body = html_to_text(body)

    attachments = []
    for part in msg.iter_attachments():
        name = part.get_filename() or "attachment"
        payload = part.get_payload(decode=True) or b""
        if name.lower().endswith(".pdf") or part.get_content_type() == "application/pdf":
            try:
                att = pdf_to_text(payload)
                att.name = name
            except Exception as err:  # a broken PDF must not stop the pipeline
                att = Attachment(name=name, text=f"[PDF could not be read: {err}]")
            attachments.append(att)
        elif part.get_content_maintype() == "text":
            attachments.append(Attachment(name=name, text=part.get_content()))

    # Message-ID identifies the email; fall back to a content hash if it is missing.
    message_id = (msg.get("Message-ID") or "").strip() or hashlib.sha256(raw).hexdigest()

    return ParsedEmail(
        message_id=message_id,
        sender_name=sender_name,
        sender_email=sender_email.lower(),
        subject=msg.get("Subject", ""),
        date=date,
        body=body.strip(),
        attachments=attachments,
    )


def email_as_text(email: ParsedEmail) -> str:
    """Single text block that is shown to the LLM and in the UI."""
    lines = [
        f"From: {email.sender_name} <{email.sender_email}>",
        f"Date: {email.date.isoformat() if email.date else 'unknown'}",
        f"Subject: {email.subject}",
        "",
        email.body,
    ]
    for att in email.attachments:
        lines += ["", f"===== ATTACHMENT: {att.name} =====", att.text]
    return "\n".join(lines)
