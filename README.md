# KBank Email Report Processing System

Automated system for processing K-Merchant and KBank eWallet email reports, extracting relevant data, loading it into Supabase, and archiving files to Google Drive.

## Features
- Fetches K-Merchant report emails (ZIP attachments with CSVs) and KBank eWallet report emails (CSVs and PDFs) from Gmail using a service account.
- Downloads and extracts K-Merchant ZIP attachments.
- Processes K-Merchant CSVs: extracts transaction summary data.
- Processes KBank eWallet CSVs: extracts 'MERCHANT TOTAL' row data.
- Loads extracted data from both K-Merchant and eWallet CSVs into a Supabase database, distinguishing them by `report_source_type`.
- Archives original K-Merchant ZIPs, their extracted contents, eWallet CSVs, and eWallet E-Tax PDFs to Google Drive, organized by Year/Month/Day.
- Implements a "replace" strategy for Google Drive uploads to ensure the latest version of a file is stored if reprocessed.
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
| ADMIN_EMAIL                      | Email for admin notifications                    |
| GOOGLE_SERVICE_ACCOUNT_KEY_PATH  | Path to service account JSON (default: service_account.json) |

## Usage
- The app will process new K-Merchant (ZIP/CSV) and KBank eWallet (CSV/PDF) report emails, extract and load data, and archive files to Google Drive.
- Processed emails are labeled in Gmail to avoid reprocessing.
- Logs are output to the console.

## Troubleshooting
- **Service account errors:** Ensure the JSON is valid and the secret is set correctly in GitHub.
- **Google Drive permissions:** The service account must have access to the target folder.
- **Supabase errors:** Check your URL and key, and ensure the database schema (e.g., `merchant_transaction_summaries` table with `report_source_type` column) matches expectations.
- **ZIP extraction issues:** Confirm the password is correct and the K-Merchant ZIP files are not corrupted.
- **eWallet CSV parsing issues:** Verify CSV format and column mapping for the 'MERCHANT TOTAL' row in `src/main.py` if data appears incorrect in Supabase.

## License
MIT 