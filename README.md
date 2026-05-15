# KBank Email Report Processing System

Automated system for processing K-Merchant, KBank eWallet, and ShopeePay email reports, extracting relevant data, loading it into Supabase, and archiving files to Google Drive.

## Features
- Fetches K-Merchant report emails (ZIP attachments with CSVs), KBank eWallet report emails (CSVs and PDFs), and ShopeePay daily settlement emails (HTML body) from Gmail using a service account.
- Downloads and extracts K-Merchant ZIP attachments.
- Processes K-Merchant CSVs: extracts transaction summary data.
- Processes KBank eWallet CSVs: extracts 'MERCHANT TOTAL' row data.
- Processes ShopeePay daily settlement emails: parses Thai-language HTML body for gross / commission / VAT / WHT / net amounts and writes one row per settlement date to `finance.shopeepay_daily_settlements`.
- Loads extracted data from both K-Merchant and eWallet CSVs into a Supabase database, distinguishing them by `report_source_type`.
- Archives original K-Merchant ZIPs, their extracted contents, eWallet CSVs, eWallet E-Tax PDFs, and ShopeePay email bodies to Google Drive, organized by Year/Month/Day.
- Implements a "replace" strategy for Google Drive uploads to ensure the latest version of a file is stored if reprocessed.
- Idempotent across reruns: K-Merchant and eWallet dedup by file hash; ShopeePay dedups by `UNIQUE(settlement_date)` plus Gmail label.
- Runs automatically via GitHub Actions (scheduled or manual).

## Setup

### 1. Local Development
1. **Clone the repository:**
   ```bash
   git clone https://github.com/david2928/kbank_fee_extract.git
   cd kbank_fee_extract
   ```
2. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment variables:**
   - Copy `.env.example` to `.env` and fill in the required values (see below).
   - Place your `service_account.json` in the project root (or set the path via `GOOGLE_SERVICE_ACCOUNT_KEY_PATH`).
5. **Run the application:**
   ```bash
   python -m src.main
   ```

### 2. GitHub Actions (CI/CD)
- The workflow is defined in `.github/workflows/main.yml`.
- It runs on push to `main`, on manual dispatch, and daily at 7:00am Thailand time (00:00 UTC).
- **Required GitHub Secrets:**
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `ZIP_PASSWORD`
  - `GMAIL_USER_EMAIL`
  - `GDRIVE_ROOT_FOLDER_ID`
  - `ADMIN_EMAIL`
  - `GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_JSON` (contents of your service account JSON)

## Environment Variables
| Variable                        | Description                                      |
|----------------------------------|--------------------------------------------------|
| SUPABASE_URL                     | Supabase project URL                             |
| SUPABASE_KEY                     | Supabase service role or anon key                |
| ZIP_PASSWORD                     | Password for K-Merchant ZIP attachments (eWallet reports do not require a password)          |
| GMAIL_USER_EMAIL                 | Gmail address to impersonate (service account needs delegation for this)                    |
| GDRIVE_ROOT_FOLDER_ID            | Google Drive folder ID for archiving             |
| GDRIVE_SHOPEEPAY_ROOT_FOLDER_ID  | Optional. Override the ShopeePay archive root. If unset, a `ShopeePay` sibling is auto-created under `GDRIVE_ROOT_FOLDER_ID` on first run. |
| ADMIN_EMAIL                      | Email for admin notifications                    |
| GOOGLE_SERVICE_ACCOUNT_KEY_PATH  | Path to service account JSON (default: service_account.json) |

## Usage
- The app will process new K-Merchant (ZIP/CSV), KBank eWallet (CSV/PDF), and ShopeePay (HTML body) report emails, extract and load data, and archive files to Google Drive.
- Processed emails are labeled in Gmail to avoid reprocessing.
- Logs are output to the console.

### ShopeePay reconciliation validation
After a backfill, every ShopeePay deposit on the KBank Savings account should equal a settlement row's `net_amount`:

```sql
SELECT b.transaction_date, b.deposit, s.settlement_date, s.net_amount,
       (b.deposit - s.net_amount) AS gap
FROM finance.bank_statement_transactions b
LEFT JOIN finance.shopeepay_daily_settlements s
  ON s.settlement_date = b.transaction_date - INTERVAL '1 day'
WHERE b.details ILIKE 'From X2131 SHOPEEPAY%'
  AND b.transaction_date >= '2026-04-01'
ORDER BY b.transaction_date;
```

Pass criteria: `gap = 0` for every row.

## Troubleshooting
- **Service account errors:** Ensure the JSON is valid and the secret is set correctly in GitHub.
- **Google Drive permissions:** The service account must have access to the target folder.
- **Supabase errors:** Check your URL and key, and ensure the database schema (e.g., `merchant_transaction_summaries` table with `report_source_type` column) matches expectations.
- **ZIP extraction issues:** Confirm the password is correct and the K-Merchant ZIP files are not corrupted.
- **eWallet CSV parsing issues:** Verify CSV format and column mapping for the 'MERCHANT TOTAL' row in `src/main.py` if data appears incorrect in Supabase.
- **ShopeePay parser returns None:** Confirm the email body is HTML and contains the Thai section header `สรุปยอดรายการโอนเงินให้ทางร้านค้า`. Re-run with the Gmail label `SHOPEEPAY_EMAIL_FAILED` removed to retry. WHT is informational only — `net = gross - refund + merchant_support - commission - vat + rollover` is the empirical equation; do not subtract WHT.

## License
MIT 