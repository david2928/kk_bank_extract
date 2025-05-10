## Design Document: K-Merchant Email Report Processing System

**Version:** 1.0
**Date:** May 21, 2024

### 1. Introduction

**1.1 Purpose**
The K-Merchant Email Report Processing System aims to automate the retrieval, extraction, and storage of transaction and fee data from daily/periodic emails sent by Kasikornbank. The system will process attached ZIP files containing CSV reports, extract relevant financial information, and populate a Supabase database for easy access and analysis.

**1.2 Scope**
*   Periodically scan a designated Gmail account for new K-Merchant report emails.
*   Download and extract ZIP file attachments (password protected).
*   Identify and parse specific CSV files for transaction and summary data.
*   Store extracted data into structured tables in a Supabase database.
*   Organize processed files for archival and reference.

**1.3 Key Data Points to Extract**
The system will focus on extracting main levels of detail from the CSV:

*   **Transaction Summary Level (from `TAX_SUMMARY_BY_TAX_ID_CSV_...csv`):**
    *   Process Date
    *   Trans Item (Nature/Count of transactions summarized)
    *   Total Amount
    *   Total Fee/Commission Amount
    *   VAT (on fee/commission)
    *   Net Debit Amount
    *   Net Credit Amount
    *   WHT Tax

### 2. System Architecture

**2.1 High-Level Overview**
The system will consist of the following main modules:

1.  **Email Monitor & Downloader:** Connects to Gmail, identifies relevant emails, and downloads ZIP attachments.
2.  **ZIP Extractor:** Unzips the downloaded files using the provided password.
3.  **File Dispatcher & Organizer:** Identifies the specific report files (CSV) and organizes them into a structured directory.
4.  **Data Extractor:** Parses the content of the identified CSV files.
5.  **Database Loader:** Inserts the extracted data into designated Supabase tables.
6.  **Scheduler:** Manages the periodic execution of the email checking process.

**2.2 Data Flow Diagram**
```
[Gmail Inbox] --(New Email with "K-Merchant Reports" subject)--> [1. Email Monitor & Downloader]
                                                                      |
                                                                      --(ZIP Attachment)--> [2. ZIP Extractor]
                                                                                              | (Password: 07013)
                                                                                              --(Extracted Files: *.csv)--> [3. File Dispatcher & Organizer]
                                                                                                                                  |
                                                                                                   (TAX_SUMMARY_BY_TAX_ID_CSV_...csv)
                                                                                                    v
                                                                                            [4a. CSV Data Extractor]
                                                                                                    |
                                                                                                    (Structured Data)
                                                                                                    v
                                                                                            [5. Database Loader]
                                                                                                    |
                                                                                                    v
                                                                                            [Supabase Database]
                                                                                                    |
                                                                                            [Processed Files Archive]
```

### 3. Detailed Component Design

**3.1 Email Monitor & Downloader**
*   **Technology:** Python (using `google-api-python-client` for Gmail API or a library like `imap_tools`).
*   **Functionality:**
    *   Securely authenticate with the Gmail account (OAuth2 recommended).
    *   Periodically scan for unread emails matching the subject: `K-Merchant Reports as of DD/MM/YYYY MERCHANT_ID` (e.g., "K-Merchant Reports as of 09/05/2025 401016061365001").
    *   Filter emails based on sender if necessary.
    *   Download the attached ZIP file (e.g., `401016061365001_Card_20250508.zip`).
    *   Mark processed emails as read or move to a specific folder.
*   **Input:** Gmail credentials, search criteria.
*   **Output:** Downloaded ZIP file.

**3.2 ZIP Extractor**
*   **Technology:** Python (using `zipfile` library).
*   **Functionality:**
    *   Extract contents of the ZIP file using the password `07013`.
    *   Place extracted files into a temporary processing directory.
*   **Input:** Path to ZIP file, password.
*   **Output:** Extracted CSV files.

**3.3 File Dispatcher & Organizer**
*   **Functionality:**
    *   Identify the key files from the extracted content:
        *   `TAX_SUMMARY_BY_TAX_ID_CSV_[TAX_ID]_[DATE].csv`
        *   `E-TAX_INVOICE_CARD_[MERCHANT_ID]_[INVOICE_NUM]_[DATE].PDF` (primarily for archival).
    *   Create a structured directory for storing processed files (original ZIP and extracted contents):
        `base_folder/reports/[merchant_id]/[report_date_YYYY-MM-DD]/`
    *   Move the ZIP and its contents to this archival location after successful processing.
*   **Input:** Paths to extracted files.
*   **Output:** Organized files, paths to specific report files for data extraction.

**3.4 Data Extractor**
    **3.4.1 CSV Data Extractor (`TAX_SUMMARY_BY_TAX_ID_CSV_...csv`)**
    *   **Technology:** Python (using `pandas` or `csv` module).
    *   **Functionality:**
        *   Read the CSV file.
        *   Extract data from columns based on headers visible in the provided screenshot (`PROCESS DATE`, `TRANS ITEM`, `TOTAL AMT`, `TOTAL FEE/COMMISSION AMOUNT`, `VAT`, `NET DEBIT AMT`, `NET CREDIT AMT`, `WHT TAX`, etc.).
    *   **Input:** Path to the CSV file.
    *   **Output:** Structured data (e.g., list of dictionaries) for the "Transaction Summary Level".

**3.5 Database Loader**
*   **Technology:** Python (using `supabase-py` client library).
*   **Functionality:**
    *   Connect to the Supabase project.
    *   Insert extracted data into the pre-defined tables (see Section 4: Data Model).
    *   Implement idempotency: Check if data for a specific report (e.g., based on merchant ID and report date/process date) already exists to prevent duplicates. This could involve a composite unique key on the tables.
*   **Input:** Structured data from extractors, Supabase credentials.
*   **Output:** Records created/updated in Supabase.

**3.6 Scheduler**
*   **Technology:** OS-level cron job (Linux/macOS), Task Scheduler (Windows), or a Python library like `APScheduler`.
*   **Functionality:** Trigger the Email Monitor & Downloader module on a defined schedule (e.g., once daily).

### 4. Data Model (Supabase Tables)

**4.1 Table: `merchant_transaction_summaries`** (from `TAX_SUMMARY_BY_TAX_ID_CSV_...csv`)
    *   `id`: SERIAL PRIMARY KEY
    *   `merchant_id`: TEXT (e.g., 401016061365001, extracted from filename or email)
    *   `report_date`: DATE (date from email subject or zip filename, e.g., 2025-05-08)
    *   `process_date`: DATE (from "PROCESS DATE" column in CSV)
    *   `trans_item_description`: TEXT (from "TRANS ITEM" column, nature needs clarification, e.g., '6')
    *   `total_amount`: NUMERIC(15, 2) (from "TOTAL AMT")
    *   `total_fee_commission_amount`: NUMERIC(15, 2) (from "TOTAL FEE/COMMISSION AMOUNT")
    *   `vat_on_fee_amount`: NUMERIC(15, 2) (from "VAT")
    *   `net_debit_amount`: NUMERIC(15, 2) (from "NET DEBIT AMT")
    *   `net_credit_amount`: NUMERIC(15, 2) (from "NET CREDIT AMT")
    *   `wht_tax_amount`: NUMERIC(15, 2) (from "WHT TAX")
    *   `wht_code`: TEXT (from "WHT CODE")
    *   `settlement_currency`: TEXT (from "SETTLEMENT ACCOUNT CURRENCY")
    *   `source_csv_filename`: TEXT
    *   `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT now()
    *   **Unique Constraint:** (`merchant_id`, `report_date`, `process_date`)

### 5. Configuration Management
*   Store sensitive information (Gmail credentials, Supabase API key, ZIP password) securely using environment variables or a secrets management tool.
*   Application settings (email search queries, scheduling interval, file paths) in a configuration file or environment variables.
*   ZIP Password: `07013`

### 6. Folder Structure (Illustrative)
```
/app_root/
  /src/                  # Source code
    main.py
    email_handler.py
    zip_processor.py
    data_extractor.py
    db_loader.py
    config.py
  /processed_data/
    /reports/
      /[merchant_id]/
        /[report_date_YYYY-MM-DD]/  # e.g., 2025-05-08
          401016061365001_Card_20250508.zip
          E-TAX_INVOICE_CARD_401016061365001_080525E00018456_20250508.PDF
          TAX_SUMMARY_BY_TAX_ID_CSV_0105566207013_20250508.csv
  /logs/
    app.log
  .env                   # For environment variables (ignored by git)
  requirements.txt       # Python dependencies
```

### 7. Error Handling and Logging
*   Implement comprehensive logging for all stages (email fetching, extraction, DB loading).
*   Retry mechanisms for network-dependent operations (Gmail, Supabase).
*   Graceful handling of missing files within the ZIP, unexpected file formats, or changes in report structure.
*   Notifications (e.g., email to admin) for critical failures or if manual intervention is needed.

### 8. Security Considerations
*   **Gmail Access:** Use OAuth2 for authentication, requesting minimal necessary permissions.
*   **Supabase Access:** Use a Supabase service role key with appropriate row-level security (RLS) if applicable, and store it securely.
*   **Password Management:** The ZIP password should be stored securely, not hardcoded directly in scripts if possible (e.g., use environment variables).
*   **Input Validation:** Sanitize filenames and any data before using it in system commands or queries.

### 9. Deployment
*   The application can be deployed as a scheduled script on a server (Linux/Windows).
*   Alternatively, for a serverless approach, components could be adapted to run as cloud functions (e.g., AWS Lambda, Google Cloud Functions) triggered by a cloud scheduler and event (e.g., new file in a bucket).

### 10. Assumptions & Points for Clarification
*   **Email Subject Consistency:** Assumes the email subject line `K-Merchant Reports as of DD/MM/YYYY MERCHANT_ID` is consistent.
*   **"Trans Item" in CSV:** The exact meaning of the "TRANS ITEM" column in the CSV (e.g., '6' in the screenshot) needs clarification to ensure correct interpretation and storage. It might be a count of transaction types or some other category.
*   **Redundancy of `E-TAX_INVOICE_CARD_...PDF`:** Assumed this PDF is for archival/cross-reference and primary data extraction will be from the CSV. If it contains unique, required data, its parsing needs to be incorporated.
*   **Report Structure Stability:** The design relies on the current structure of the CSV files. Significant changes to these formats would require updates to the parsing logic.

### 11. Future Enhancements
*   Development of a web interface for monitoring, manual uploads, and viewing processed data.
*   Advanced alerting for parsing errors or missing reports.
*   Support for additional report types or formats from other sources.
*   Automated reconciliation features. 