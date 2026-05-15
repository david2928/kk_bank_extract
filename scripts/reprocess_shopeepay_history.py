"""
One-shot: remove SHOPEEPAY_EMAIL_PROCESSED label from all ShopeePay emails so
the next `python -m src.main` run reprocesses them. Use after a parser/loader
change that requires re-ingesting historical data (e.g. switching raw_body
from stripped text to raw HTML).

Idempotent — the next main() run skips Drive uploads for rows whose
gdrive_file_id is already set.

Usage:
    python -m scripts.reprocess_shopeepay_history
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import email_handler


def main():
    svc = email_handler.get_gmail_service()
    if svc is None:
        print("ERROR: Gmail auth failed.", file=sys.stderr)
        sys.exit(1)

    query = f"from:support_th@shopeepay.com label:{email_handler.LABEL_SHOPEEPAY_EMAIL_PROCESSED}"
    messages = email_handler.search_emails(svc, query)
    print(f"Found {len(messages)} messages carrying {email_handler.LABEL_SHOPEEPAY_EMAIL_PROCESSED}")
    for m in messages:
        ok = email_handler.remove_label_from_email(
            svc, m["id"], email_handler.LABEL_SHOPEEPAY_EMAIL_PROCESSED
        )
        print(f"  {m['id']}: removed_label={ok}")


if __name__ == "__main__":
    main()
