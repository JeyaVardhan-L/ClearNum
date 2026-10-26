"""Local MBOX email archive analyzer.
Parses user-authorized email exports (.mbox) in local memory to discover
commercial subscriptions, List-Unsubscribe headers, and exposed phone numbers.
"""

import mailbox
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from email.header import decode_header
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.matcher import match_phone_in_text


@dataclass
class DiscoveredSubscription:
    sender_name: str
    sender_contact: str
    channel: str  # "EMAIL", "SMS"
    unsubscribe_method: str  # "HEADER_URL", "HEADER_MAILTO", "BODY_LINK", "SMS_STOP"
    unsubscribe_target: str
    subject_sample: str
    phone_exposed: bool
    evidence_snippet: str


def decode_mime_header(header_value: Optional[str]) -> str:
    """Safely decodes RFC 2047 MIME encoded headers."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result)
    except Exception:
        return str(header_value)


def extract_unsubscribe_links(list_unsubscribe_header: str) -> tuple[Optional[str], Optional[str]]:
    """Extracts HTTP URL and mailto links from a List-Unsubscribe header.
    Format: <https://example.com/unsub>, <mailto:unsub@example.com?subject=unsub>
    """
    if not list_unsubscribe_header:
        return None, None
    
    http_link = None
    mailto_link = None
    
    matches = re.findall(r"<([^>]+)>", list_unsubscribe_header)
    for m in matches:
        if m.startswith(("http://", "https://")) and not http_link:
            http_link = m
        elif m.startswith("mailto:") and not mailto_link:
            mailto_link = m
            
    return http_link, mailto_link


def parse_mbox_file(file_path: Path | str, phone: Optional[NormalizedPhone] = None, max_emails: int = 500) -> List[DiscoveredSubscription]:
    """Parses a local .mbox file and returns discovered commercial subscriptions
    and whether the target phone appears in email bodies.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MBOX file not found at: {file_path}")

    subscriptions: List[DiscoveredSubscription] = []
    seen_senders = set()

    mbox = mailbox.mbox(str(path))
    count = 0

    for msg in mbox:
        count += 1
        if count > max_emails:
            break

        from_header = decode_mime_header(msg.get("From", ""))
        subject = decode_mime_header(msg.get("Subject", ""))
        unsub_header = msg.get("List-Unsubscribe", "")
        
        # Extract sender email
        email_match = re.search(r"[\w.-]+@[\w.-]+\.\w+", from_header)
        sender_email = email_match.group(0).lower() if email_match else from_header
        
        if not sender_email or sender_email in seen_senders:
            continue

        # Extract message body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type in ("text/plain", "text/html"):
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode(part.get_content_charset() or "utf-8", errors="replace") + " "
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                pass

        # Check for unsubscribe header or body keywords
        http_unsub, mailto_unsub = extract_unsubscribe_links(unsub_header)
        unsub_method = "NONE"
        unsub_target = ""

        if http_unsub:
            unsub_method = "HEADER_URL"
            unsub_target = http_unsub
        elif mailto_unsub:
            unsub_method = "HEADER_MAILTO"
            unsub_target = mailto_unsub
        elif "unsubscribe" in body.lower():
            # Extract basic link or opt-out keyword
            link_match = re.search(r'https?://[^\s<>"]+unsub[^\s<>"]*', body, re.IGNORECASE)
            if link_match:
                unsub_method = "BODY_LINK"
                unsub_target = link_match.group(0)

        # Check if phone number is exposed in this email
        phone_exposed = False
        snippet = ""
        if phone and phone.is_possible:
            match_res = match_phone_in_text(body, phone)
            if match_res.matched:
                phone_exposed = True
                snippet = match_res.snippet

        if unsub_method != "NONE" or phone_exposed:
            seen_senders.add(sender_email)
            subscriptions.append(DiscoveredSubscription(
                sender_name=from_header.split("<")[0].strip().replace('"', '') or sender_email,
                sender_contact=sender_email,
                channel="EMAIL",
                unsubscribe_method=unsub_method,
                unsubscribe_target=unsub_target,
                subject_sample=subject[:80],
                phone_exposed=phone_exposed,
                evidence_snippet=snippet[:150] if snippet else f"Found commercial subscription headers in email from {sender_email}",
            ))

    return subscriptions
