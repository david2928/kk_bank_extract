"""
Backfill tax_invoice_no on EWALLET_CSV summary rows by re-parsing every
EWALLET_ETAX PDF already archived in Google Drive.

GDrive layout walked: <root>/YYYY/YYYYMM/YYYY-MM-DD/E-TAX_INVOICE_EWALLET_<merchant>_DDMMYYYY.pdf

Usage:
    python -m scripts.backfill_ewallet_invoice_numbers [--dry-run] [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Idempotent: skips PDFs whose corresponding EWALLET_CSV row already has a
non-NULL tax_invoice_no, and skips PDFs with no matching CSV row at all.
"""

import argparse
import logging
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, date

# Allow running as `python scripts/backfill_ewallet_invoice_numbers.py` from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src import gdrive_handler
from src.data_extractor import extract_ewallet_etax_pdf_data
from src.db_loader import (
    get_supabase_client,
    get_ewallet_csv_summary,
    update_ewallet_csv_tax_invoice_no,
)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FOLDER_MIME = 'application/vnd.google-apps.folder'
PDF_FILENAME_PATTERN = re.compile(r"^E-TAX_INVOICE_EWALLET_(\d+)_(\d{8})\.pdf$", re.IGNORECASE)


def _parse_iso_date(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _iter_etax_pdfs(gdrive_service, root_folder_id, date_from=None, date_to=None):
    """Yields (day_str, file) for every ETAX PDF under root, filtered by date range."""
    year_entries = gdrive_handler.list_files_in_folder(gdrive_service, root_folder_id)
    for year_entry in year_entries:
        if year_entry.get('mimeType') != FOLDER_MIME:
            continue
        if not re.fullmatch(r"\d{4}", year_entry['name']):
            continue
        month_entries = gdrive_handler.list_files_in_folder(gdrive_service, year_entry['id'])
        for month_entry in month_entries:
            if month_entry.get('mimeType') != FOLDER_MIME:
                continue
            if not re.fullmatch(r"\d{6}", month_entry['name']):
                continue
            day_entries = gdrive_handler.list_files_in_folder(gdrive_service, month_entry['id'])
            for day_entry in day_entries:
                if day_entry.get('mimeType') != FOLDER_MIME:
                    continue
                day_name = day_entry['name']
                try:
                    day_date = datetime.strptime(day_name, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if date_from and day_date < date_from:
                    continue
                if date_to and day_date > date_to:
                    continue
                files = gdrive_handler.list_files_in_folder(gdrive_service, day_entry['id'])
                for f in files:
                    if f.get('mimeType') == FOLDER_MIME:
                        continue
                    if PDF_FILENAME_PATTERN.match(f['name']):
                        yield day_name, f


def main():
    parser = argparse.ArgumentParser(description="Backfill tax_invoice_no from archived EWALLET ETAX PDFs.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report only; do not update Supabase.")
    parser.add_argument("--from", dest="date_from", help="Inclusive lower bound (YYYY-MM-DD) on day folder.")
    parser.add_argument("--to", dest="date_to", help="Inclusive upper bound (YYYY-MM-DD) on day folder.")
    args = parser.parse_args()

    date_from = _parse_iso_date(args.date_from)
    date_to = _parse_iso_date(args.date_to)

    logger.info("Initializing Google Drive service...")
    gdrive_service = gdrive_handler.get_gdrive_service()
    if not gdrive_service:
        logger.error("Failed to initialize Google Drive service. Aborting.")
        return 1

    logger.info("Initializing Supabase client...")
    supabase_client = get_supabase_client()
    if not supabase_client:
        logger.error("Failed to initialize Supabase client. Aborting.")
        return 1

    counters = {
        "scanned": 0,
        "skipped_already_set": 0,
        "skipped_no_csv": 0,
        "updated": 0,
        "parse_failed": 0,
        "download_failed": 0,
    }

    tmp_dir = tempfile.mkdtemp(prefix="ewallet_etax_backfill_")
    logger.info(f"Using temp dir: {tmp_dir}")

    try:
        for day_str, gdrive_file in _iter_etax_pdfs(gdrive_service, config.GDRIVE_ROOT_FOLDER_ID, date_from, date_to):
            counters["scanned"] += 1
            filename = gdrive_file['name']
            match = PDF_FILENAME_PATTERN.match(filename)
            if not match:
                continue
            merchant_id = match.group(1)
            ddmmyyyy = match.group(2)
            try:
                process_date_obj = datetime.strptime(ddmmyyyy, "%d%m%Y").date()
            except ValueError:
                logger.warning(f"Skipping {filename}: cannot parse date '{ddmmyyyy}'.")
                continue
            process_date_str = process_date_obj.strftime("%Y-%m-%d")

            csv_row = get_ewallet_csv_summary(merchant_id, process_date_str)
            if not csv_row:
                logger.info(
                    f"[skip:no_csv] {filename} (merchant_id={merchant_id} process_date={process_date_str})"
                )
                counters["skipped_no_csv"] += 1
                continue
            if csv_row.get("tax_invoice_no"):
                counters["skipped_already_set"] += 1
                continue

            local_path = os.path.join(tmp_dir, filename)
            if not gdrive_handler.download_file_to_local(gdrive_service, gdrive_file['id'], local_path):
                logger.error(f"[download_failed] {filename}")
                counters["download_failed"] += 1
                continue

            try:
                parsed = extract_ewallet_etax_pdf_data(local_path)
                if not parsed:
                    logger.error(f"[parse_failed] {filename}")
                    counters["parse_failed"] += 1
                    continue

                if args.dry_run:
                    logger.info(
                        f"[dry-run] would update merchant_id={merchant_id} process_date={process_date_str} "
                        f"tax_invoice_no={parsed['tax_invoice_no']}"
                    )
                    counters["updated"] += 1
                    continue

                rows_updated = update_ewallet_csv_tax_invoice_no(
                    merchant_id=merchant_id,
                    process_date=process_date_str,
                    tax_invoice_no=parsed['tax_invoice_no'],
                )
                if rows_updated >= 1:
                    counters["updated"] += 1
                else:
                    # Race: row got a value between the SELECT and UPDATE — treat as already_set.
                    counters["skipped_already_set"] += 1
            finally:
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except OSError as e:
                    logger.warning(f"Could not remove temp file {local_path}: {e}")
    finally:
        # rmtree handles the case where a partial download left bytes behind.
        shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info("--- Backfill summary ---")
    for k, v in counters.items():
        logger.info(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
