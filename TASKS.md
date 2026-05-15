# Project Tasks

This document tracks the tasks for the KBank Report Processing application.

## Epic: P0-INIT - Initial Project Setup
*   **P0-TASK-001 (Project Scaffolding):**
    *   **Description:** Initialize project structure, version control, and basic dependencies.
    *   **Status:** Done
*   **P0-TASK-002 (Core Configuration):**
    *   **Description:** Set up `.env` and `src/config.py` for managing secrets and configurations.
    *   **Status:** Done

## Epic: P1-REPORTS - K-Merchant Report Processing (Original ZIP/CSV/PDF)
*   **P1-TASK-001 (CSV Parser):**
    *   **Description:** Implement CSV parsing logic for K-Merchant summary reports.
    *   **Status:** Done
*   **P1-TASK-002 (PDF Parser):**
    *   **Description:** Implement PDF parsing logic for K-Merchant detailed transaction reports (KB1P554V2_SUM).
    *   **Status:** Done (but later commented out/deprioritized based on `main.py` review)
*   **P1-TASK-003 (Supabase Loader):**
    *   **Description:** Implement `src/db_loader.py` to load extracted data into Supabase tables.
    *   **Status:** Done
*   **P1-TASK-004 (ZIP Extractor):**
    *   **Description:** Implement logic to extract files from password-protected ZIP archives.
    *   **Status:** Done

## Epic: P2-EMAIL - Integrate Gmail Fetching and File Organization
*   **P2-TASK-001 (Gmail OAuth/Service Account Setup):**
    *   **Description:** Set up Google Cloud Project, enable Gmail API, configure service account for impersonation.
    *   **Status:** Done
*   **P2-TASK-002 (Email Monitor & Downloader):**
    *   **Description:** Implement `email_handler.py` to connect to Gmail, find relevant K-Merchant ZIP emails, and download attachments.
    *   **Status:** Done
*   **P2-TASK-003 (Google Drive Integration):**
    *   **Description:** Implement `gdrive_handler.py` to upload files to a structured Google Drive folder.
    *   **Status:** Done
*   **P2-TASK-004 (Integrate Email Handling into Main):**
    *   **Description:** Update `main.py` to use `email_handler.py` and `gdrive_handler.py` for the original K-Merchant ZIP reports.
    *   **Status:** Done

## Epic: P3-EWALLET - KBank eWallet Report Integration

*   **P3-TASK-001 (Analyze eWallet Reports):**
    *   **Description:** Analyze the structure of eWallet CSV and PDF reports. Confirm data fields, merchant ID source, and date interpretations.
    *   **Status:** In Progress
*   **P3-TASK-002 (Supabase Schema Update - `merchant_transaction_summaries`):**
    *   **Description:** Add a new column (e.g., `report_source_type TEXT`) to the `merchant_transaction_summaries` table to distinguish eWallet data. Document the DDL change.
    *   **Instruction for User:** `ALTER TABLE merchant_transaction_summaries ADD COLUMN report_source_type TEXT;`
    *   **Status:** Done
*   **P3-TASK-003 (Update `src/email_handler.py` for eWallet):**
    *   **Description:** Add new Gmail labels (e.g., `EWALLET_CSV_PROCESSED`, `EWALLET_ETAX_PDF_PROCESSED`). Modify `fetch_new_reports` to be generic: it should accept an `attachment_config` (defining search query details, desired filename extension, `report_type` identifier like 'EWALLET_CSV', 'ETAX_PDF', 'KMERCHANT_ZIP', and the key for the file path in the result). It should return this `report_type` and use a consistent file path key in its results. `download_specific_attachments` will be used as is. Update logging in relevant functions.
    *   **Status:** Done
*   **P3-TASK-004 (Implement eWallet CSV Processing in `src/main.py`):**
    *   **Description:** Create `process_ewallet_csv()` function. This includes:
        *   Parsing the CSV to find the "MERCHANT TOTAL" row.
        *   Extracting relevant data (Merchant ID, Report Date, Process Date, Comm, VAT, Net, Sale).
        *   Mapping data to `merchant_transaction_summaries` fields (including `report_source_type='EWALLET_CSV'`).
        *   Calling `db_loader.load_merchant_transaction_summaries()`.
        *   Calling `gdrive_handler.upload_file_to_gdrive()` for the CSV.
        *   Calling `email_handler.add_label_to_email()` for the processed email.
    *   **Status:** Done
*   **P3-TASK-005 (Implement eWallet E-Tax PDF Processing in `src/main.py`):**
    *   **Description:** Create `process_ewallet_etax_pdf()` function. This includes:
        *   Calling `gdrive_handler.upload_file_to_gdrive()` for the PDF.
        *   Calling `email_handler.add_label_to_email()` for the processed email.
    *   **Status:** Done
*   **P3-TASK-006 (Integrate eWallet Processing into `main()` in `src/main.py`):**
    *   **Description:** Update the `main()` function in `src/main.py`:
        *   Call the modified `email_handler.fetch_new_reports` multiple times with different `attachment_config` arguments (for K-Merchant ZIPs, eWallet CSVs, eWallet PDFs).
        *   Modify the main processing loop to inspect the `report_type` of each fetched item.
        *   Based on `report_type`, dispatch to the correct processing function:
            *   `process_single_zip()` (for K-Merchant ZIPs - adapt if the structure of data returned by `fetch_new_reports` changes, e.g., file path key).
            *   `process_ewallet_csv()` (new, for eWallet CSVs).
            *   `process_ewallet_etax_pdf()` (new, for eWallet PDFs).
        *   Also involves adapting `src/data_extractor.py`'s `extract_csv_data` function to handle `report_source_type`.
    *   **Status:** Done
*   **P3-TASK-007 (Testing and Validation):**
    *   **Description:** Perform unit and integration testing for the new eWallet report processing. Verify data in Supabase, files in Google Drive, and email labeling.
    *   **Status:** To Do
*   **P3-TASK-008 (Documentation Update):**
    *   **Description:** Update `README.md` and any other relevant documentation to reflect the new eWallet report handling capabilities.
    *   **Status:** To Do

## Epic: P4-SHOPEEPAY - ShopeePay Daily Settlement Email Integration

ShopeePay (payment-link aggregator) sends a daily Thai-language HTML email from
`support_th@shopeepay.com` summarising the previous day's gross / commission /
VAT / WHT / net for settlement to KBank Savings 170-3-27029-4 on T+1. This
pipeline ingests those emails into `finance.shopeepay_daily_settlements`.
Empirical formula: `net = gross - refund + merchant_support - commission - vat`
(WHT is informational only — NOT subtracted from the deposit).

*   **P4-TASK-001 (Analyze ShopeePay emails):**
    *   **Description:** Read-only probe of `support_th@shopeepay.com` since 2026-04-01 to confirm cadence, format, attachments-vs-body, second-section ambiguity, and duplicate-resend behaviour.
    *   **Findings:** 8 emails / 7 distinct settlement dates (one duplicate-resend on 2026-04-30, identical content, 13 min apart). All HTML-only (no `text/plain`, no attachments). Subject pattern `[LENGOLF...] รายงานการโอนเงินสำหรับ ShopeePay Payment [YYYY-MM-DD]` (delivery date). Bank tail `******0294` literal in all. WHT is shown but NOT subtracted from the deposit (contradicts initial spec).
    *   **Status:** Done
*   **P4-TASK-002 (Supabase schema):**
    *   **Description:** Create `finance.shopeepay_daily_settlements` with `UNIQUE(settlement_date)` so duplicate-resend emails upsert into the same row.
    *   **Migration:** `migrations/2026-05-15_shopeepay_daily_settlements.sql`
    *   **Status:** Done
*   **P4-TASK-003 (Email handler — body-only fetcher):**
    *   **Description:** Add `LABEL_SHOPEEPAY_EMAIL_PROCESSED` / `LABEL_SHOPEEPAY_EMAIL_FAILED`. Add `fetch_new_body_only_reports(service, search_query, processed_label)` which returns decoded `body_text` (HTML stripped to text) + `message_id` without downloading attachments. No changes to the existing attachment-based `fetch_new_reports`.
    *   **Status:** Done
*   **P4-TASK-004 (Parser):**
    *   **Description:** Add `extract_shopeepay_settlement_body(body_text, subject)` to `src/data_extractor.py`. Accepts HTML or already-stripped text. Truncates at the "not-yet-collected" second-table header before applying regex so the same field labels in the second section can't poison the result. Settlement date derived from `ประจำวันที่ X - X` in body, with subject-date fallback (`[YYYY-MM-DD]` minus one day).
    *   **Tests:** `tests/test_shopeepay_parser.py` (5 tests).
    *   **Status:** Done
*   **P4-TASK-005 (Loader):**
    *   **Description:** Add `load_shopeepay_settlements(data_list)` to `src/db_loader.py`. Upsert with `on_conflict='settlement_date'`.
    *   **Status:** Done
*   **P4-TASK-006 (Main wire-up):**
    *   **Description:** Add `process_shopeepay_email(report_info, gdrive_service, supabase_client)`. Archives the raw HTML body to Drive under `<root>/ShopeePay/YYYY/YYYYMM/YYYY-MM-DD/shopeepay-settlement-YYYY-MM-DD.txt` (root override via `GDRIVE_SHOPEEPAY_ROOT_FOLDER_ID` env, else auto-creates a `ShopeePay` sibling under `GDRIVE_ROOT_FOLDER_ID`). Dispatcher block added in `main()` after the attachment-based loop; the early-return-when-empty was relaxed so body-only paths still run.
    *   **Status:** Done
*   **P4-TASK-007 (Backfill + validate):**
    *   **Description:** Full backfill via `python -m src.main`. Confirm all 6 known ShopeePay deposits (2026-04-16 → 2026-05-09) reconcile to a settlement row's `net_amount` with `gap = 0`.
    *   **Result:** 8 emails fetched → 7 rows (duplicate-resend collapsed); all 6 known deposits verified with `gap = 0.00`. Re-running yields 0 fetched (Gmail label idempotency).
    *   **Status:** Done
*   **P4-TASK-008 (Documentation):**
    *   **Description:** Update `README.md` Features list to mention ShopeePay daily settlement emails.
    *   **Status:** Done
