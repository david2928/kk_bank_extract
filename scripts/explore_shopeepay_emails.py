"""
One-off Step 1 investigation probe — READ-ONLY.

Reports cadence, format stability, attachment presence, subject/body shape for
every message from support_th@shopeepay.com since 2026-04-01. Does NOT write
to Supabase, apply Gmail labels, or upload to Drive.

Usage:
    python -m scripts.explore_shopeepay_emails
    python -m scripts.explore_shopeepay_emails > shopeepay_probe.txt 2>&1
"""

import base64
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import email_handler

QUERY = "from:support_th@shopeepay.com after:2026/04/01"


def _decode_part(part):
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")


def _collect_mimetype(payload, mimetype):
    """Recursively collect decoded text from all parts matching mimetype."""
    out = []
    if payload.get("mimeType") == mimetype:
        out.append(_decode_part(payload))
    for p in payload.get("parts", []) or []:
        out.extend(_collect_mimetype(p, mimetype))
    return out


def _walk_attachments(payload, acc):
    if payload.get("filename"):
        acc.append((payload["filename"], payload.get("mimeType")))
    for p in payload.get("parts", []) or []:
        _walk_attachments(p, acc)


def main():
    svc = email_handler.get_gmail_service()
    if svc is None:
        print("ERROR: get_gmail_service() returned None — auth failed.", file=sys.stderr)
        sys.exit(1)

    messages = email_handler.search_emails(svc, QUERY)
    print(f"\n{'='*80}")
    print(f"Found {len(messages)} messages matching: {QUERY}")
    print(f"{'='*80}\n")

    summary = {
        "total": len(messages),
        "with_attachments": 0,
        "body_only": 0,
        "has_text_plain": 0,
        "has_text_html_only": 0,
    }

    for m in messages:
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
        internal_ts = int(full.get("internalDate", "0")) / 1000.0
        internal_dt = datetime.fromtimestamp(internal_ts, tz=timezone.utc).isoformat()

        attachments: list = []
        _walk_attachments(full["payload"], attachments)

        plains = [p for p in _collect_mimetype(full["payload"], "text/plain") if p]
        htmls = [p for p in _collect_mimetype(full["payload"], "text/html") if p]
        plain_body = "\n".join(plains)

        if attachments:
            summary["with_attachments"] += 1
        else:
            summary["body_only"] += 1
        if plains:
            summary["has_text_plain"] += 1
        elif htmls:
            summary["has_text_html_only"] += 1

        print("-" * 80)
        print(f"id={m['id']}")
        print(f"internalDate={internal_dt}")
        print(f"From={headers.get('From')}")
        print(f"To={headers.get('To')}")
        print(f"Date={headers.get('Date')}")
        print(f"Subject={headers.get('Subject')}")
        print(f"attachments={attachments}")
        print(f"mime: text/plain parts={len(plains)}, text/html parts={len(htmls)}")
        print("body text/plain (first 60 lines):")
        if plain_body:
            for line in plain_body.splitlines()[:60]:
                print(f"  | {line}")
        else:
            print("  (no text/plain — HTML only)")
            if htmls:
                print("  text/html (first 20 lines, raw):")
                for line in htmls[0].splitlines()[:20]:
                    print(f"  H| {line}")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
