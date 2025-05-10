# Project Tasks: K-Merchant Email Report Processing System

## Phase 1: Core Data Extraction & Local Processing

### Epic: P1-CORE - Implement Core Data Extraction and Supabase Loading

*   **P1-TASK-001 (Project Setup):**
    *   **Description:** Create initial project directory structure, `requirements.txt`, `.env` template, and placeholder Python modules.
    *   **Acceptance Criteria:**
        *   Directory structure matches `DESIGN_DOCUMENT.md`.
        *   `requirements.txt` includes `pandas`, `pdfplumber` (or `tabula-py`), `zipfile`, `supabase-py`, `python-dotenv`.
        *   `.env.template` exists with placeholders for `SUPABASE_URL`, `SUPABASE_KEY`, `ZIP_PASSWORD`.
        *   Placeholder files (`main.py`, `zip_processor.py`, `data_extractor.py`, `db_loader.py`, `config.py`) are created in `/src`.
    *   **Status:** Done

*   **P1-TASK-002 (Config Loader):**
    *   **Description:** Implement `config.py` to load secrets and settings from `.env` file.
    *   **Acceptance Criteria:**
        *   `config.py` successfully loads `SUPABASE_URL`, `SUPABASE_KEY`, `ZIP_PASSWORD`.
        *   Functions exist to easily access these config values.
    *   **Status:** Done

*   **P1-TASK-003 (ZIP Extractor):**
    *   **Description:** Develop `zip_processor.py` to extract files from a password-protected ZIP archive.
    *   **Acceptance Criteria:**
        *   Function takes ZIP file path and password as input.
        *   Successfully extracts all files from a sample K-Merchant ZIP.
        *   Returns paths to the extracted files.
        *   Handles errors like incorrect password or corrupted ZIP.
    *   **Status:** Done

*   **P1-TASK-004 (CSV Data Extractor):**
    *   **Description:** Implement CSV parsing logic in `data_extractor.py` for `TAX_SUMMARY_BY_TAX_ID_CSV_...csv`.
    *   **Acceptance Criteria:**
        *   Function takes CSV file path as input.
        *   Correctly parses all required fields as per `DESIGN_DOCUMENT.md` (Section 1.3, 4.1).
        *   Returns data structured for Supabase insertion (e.g., list of dictionaries).
        *   Handles variations in date format if necessary.
        *   Unit tests pass with sample CSV data.
    *   **Status:** Done

*   **P1-TASK-006 (Supabase Schema Setup):**
    *   **Description:** Manually define and create `merchant_transaction_summaries` tables in the Supabase project.
    *   **Acceptance Criteria:**
        *   Tables are created in Supabase matching the schema in `DESIGN_DOCUMENT.md` (Section 4).
        *   Primary keys and unique constraints are correctly defined.
    *   **Status:** Done

*   **P1-TASK-007 (Database Loader):**
    *   **Description:** Develop `db_loader.py` to insert extracted data into Supabase tables.
    *   **Acceptance Criteria:**
        *   Functions take structured data (from CSV extractors) and insert it into the correct Supabase tables.
        *   Idempotency is handled (prevents duplicate entries based on unique constraints).
        *   Handles Supabase connection errors.
        *   Unit tests (mocked or against a test instance) pass.
    *   **Status:** Done

*   **P1-TASK-008 (Main Orchestration - Local):**
    *   **Description:** Create an initial `main.py` script to orchestrate the local processing workflow (unzip -> parse -> load).
    *   **Acceptance Criteria:**
        *   Script takes a local ZIP file path as an argument.
        *   Successfully processes the ZIP: extracts, parses CSV, loads data to Supabase.
        *   Basic logging of major steps.
    *   **Status:** Done

## Phase 2: Email Integration & File Management

### Epic: P2-EMAIL - Integrate Gmail Fetching and File Organization

*   **P2-TASK-001 (Gmail OAuth Setup):**
    *   **Description:** Set up Google Cloud Project, enable Gmail API, and configure OAuth2 credentials.
    *   **Acceptance Criteria:**
        *   `credentials.json` (or equivalent) obtained for Gmail API access.
        *   Token storage mechanism decided (e.g., `token.json`).
        *   Instructions for OAuth consent flow documented for first run.
    *   **Status:** Done

*   **P2-TASK-002 (Email Monitor & Downloader):**
    *   **Description:** Implement `email_handler.py` to connect to Gmail, find relevant emails, and download attachments.
    *   **Acceptance Criteria:**
        *   Authenticates with Gmail using OAuth2.
        *   Searches for unread emails matching subject criteria from `DESIGN_DOCUMENT.md`.
        *   Downloads ZIP attachments to a specified directory.
        *   Marks processed emails as read (or moves to a folder).
        *   Handles API errors and no-new-mail scenarios.
    *   **Status:** Done

*   **P2-TASK-003 (File Dispatcher & Organizer):**
    *   **Description:** Enhance `main.py` or create a new module for organizing processed files.
    *   **Acceptance Criteria:**
        *   Identifies key report files (CSV) from the extracted set.
        *   Creates archival folder structure: `processed_data/reports/[merchant_id]/[report_date_YYYY-MM-DD]/`.
        *   Moves original ZIP and all extracted contents to the archival folder.
    *   **Status:** Done

*   **P2-TASK-004 (Integrate Email Handling into Main):**
    *   **Description:** Update `main.py` to use `email_handler.py` as the source of ZIP files instead of local paths.
    *   **Acceptance Criteria:**
        *   `main.py` calls email handler to get new reports.
        *   Processes each downloaded ZIP through the existing extraction and loading pipeline.
    *   **Status:** Done

## Phase 3: Scheduling, Logging, and Error Handling

### Epic: P3-ROBUST - Enhance System Robustness and Automation

*   **P3-TASK-001 (Scheduler):**
    *   **Description:** Implement a scheduling mechanism to run the email processing job automatically.
    *   **Acceptance Criteria:**
        *   Chosen scheduler (e.g., `APScheduler` or system cron) is configured.
        *   The main processing script runs at a defined interval (e.g., daily).
    *   **Status:** To Do

*   **P3-TASK-002 (Enhanced Logging):**
    *   **Description:** Implement comprehensive logging using the `logging` module.
    *   **Acceptance Criteria:**
        *   Logs are written to both console and a rotating log file (`logs/app.log`).
        *   Logs include timestamps, severity levels, and module information.
        *   Key events, errors, and processed file details are logged.
    *   **Status:** Done

*   **P3-TASK-003 (Advanced Error Handling & Notifications):**
    *   **Description:** Improve error handling and add basic notifications for critical failures.
    *   **Acceptance Criteria:**
        *   Specific exceptions are caught and handled gracefully (e.g., parsing errors, API failures).
        *   A mechanism for sending email notifications to an admin on critical, unrecoverable errors is in place.
    *   **Status:** To Do

## Phase 4: Refinement, Testing, and Deployment Preparation

### Epic: P4-DEPLOY - Finalize and Prepare for Deployment

*   **P4-TASK-001 (End-to-End Testing):**
    *   **Description:** Conduct thorough testing of the entire system with diverse inputs.
    *   **Acceptance Criteria:**
        *   System correctly processes various sample K-Merchant emails.
        *   Edge cases (empty ZIP, missing files, malformed data) are handled as expected.
        *   Data integrity in Supabase is verified.
    *   **Status:** To Do

*   **P4-TASK-002 (Code Review & Refactoring):**
    *   **Description:** Review and refactor code for quality, performance, and maintainability.
    *   **Acceptance Criteria:**
        *   Code adheres to PEP 8 and project style guidelines.
        *   Redundant code is removed, and complex sections are simplified.
        *   Performance bottlenecks are addressed if any.
    *   **Status:** To Do

*   **P4-TASK-003 (Documentation Finalization):**
    *   **Description:** Update and finalize all project documentation.
    *   **Acceptance Criteria:**
        *   `README.md` is comprehensive with setup, configuration, execution, and troubleshooting steps.
        *   Code comments are clear and sufficient.
        *   `DESIGN_DOCUMENT.md` and `DEVELOPMENT_PLAN.md` are up-to-date.
    *   **Status:** To Do

*   **P4-TASK-004 (Deployment Package):**
    *   **Description:** Prepare the application for deployment.
    *   **Acceptance Criteria:**
        *   `requirements.txt` is finalized.
        *   Deployment strategy is decided (e.g., Dockerfile, script with virtual environment).
        *   Clear instructions for deploying and running the application are available.
    *   **Status:** To Do 