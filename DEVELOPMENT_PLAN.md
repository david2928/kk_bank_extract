## Development Plan: K-Merchant Email Report Processing System

**Version:** 1.0
**Date:** May 21, 2024

### 1. Guiding Principles
*   **Incremental Development:** Build and test components in stages.
*   **Focus on Core First:** Ensure data extraction and processing logic is solid before adding external integrations.
*   **Testability:** Write modular code that can be tested independently.
*   **Configuration Driven:** Avoid hardcoding; use configuration files or environment variables for settings.

### 2. Development Phases

**Phase 1: Core Data Extraction & Local Processing (Critical Path)**
*   **Objective:** Be able to reliably extract data from locally stored ZIP files and their contents (CSV) and load it into Supabase. This phase focuses on proving the core data transformation pipeline.
*   **Tasks:**
    1.  **Project Setup:**
        *   Create the initial directory structure as outlined in `DESIGN_DOCUMENT.md` (Section 6).
        *   Initialize a `requirements.txt` file with initial libraries (e.g., `pandas`, `zipfile`, `supabase-py`, `python-dotenv`).
        *   Set up a `.env` file for storing Supabase credentials and the ZIP password.
        *   Create placeholder Python files (`main.py`, `zip_processor.py`, `data_extractor.py`, `db_loader.py`, `config.py`).
    2.  **ZIP Extractor (`zip_processor.py`):**
        *   Implement function(s) to extract contents from a password-protected ZIP file.
        *   Input: ZIP file path, password.
        *   Output: Paths to extracted files in a temporary location.
    3.  **CSV Data Extractor (Part of `data_extractor.py`):**
        *   Implement function(s) to parse the `TAX_SUMMARY_BY_TAX_ID_CSV_...csv` file.
        *   Use `pandas` for robust CSV handling.
        *   Map CSV columns to the `merchant_transaction_summaries` data model.
        *   Handle potential variations or missing columns gracefully.
        *   Write unit tests using sample CSV data.
    4.  **Supabase Schema Setup & Database Loader (`db_loader.py`):**
        *   Manually create the `merchant_transaction_summaries` table in your Supabase project as defined in `DESIGN_DOCUMENT.md`.
        *   Implement function(s) in `db_loader.py` to connect to Supabase and insert data into the table.
        *   Implement idempotency logic (e.g., checking for existing records based on unique constraints).
        *   Write unit tests (may require mocking Supabase client or a test database instance).
    5.  **Main Orchestration Script (Initial version in `main.py`):**
        *   Create a script that takes a local ZIP file path as input.
        *   Orchestrates the calling of: ZIP Extractor -> CSV Extractor -> Database Loader.
        *   Basic logging for this phase.
    6.  **Configuration Management (`config.py`):**
        *   Implement loading of configurations (Supabase URL/Key, ZIP password) from `.env` file.

**Phase 2: Email Integration & File Management**
*   **Objective:** Automate the process of fetching emails, downloading attachments, and organizing files.
*   **Tasks:**
    1.  **Email Monitor & Downloader (`email_handler.py`):**
        *   Implement Gmail API integration (OAuth2 setup will be crucial).
        *   Functionality to search for emails based on subject and other criteria.
        *   Download ZIP attachments.
        *   Mark emails as processed.
        *   Error handling for Gmail API interactions.
        *   Unit tests (will likely require mocking Gmail service).
    2.  **File Dispatcher & Organizer (Enhance `main.py` or new module):**
        *   Implement logic to identify the specific report files (CSV) from extracted contents.
        *   Create the archival folder structure (`processed_data/reports/[merchant_id]/[report_date_YYYY-MM-DD]/`).
        *   Move original ZIP and extracted files to the archive.
    3.  **Update `main.py`:**
        *   Integrate `email_handler.py` to fetch new reports.
        *   Modify to process downloaded ZIPs instead of local paths.

**Phase 3: Scheduling, Logging, and Error Handling**
*   **Objective:** Make the system robust and autonomous.
*   **Tasks:**
    1.  **Scheduler Integration:**
        *   Choose and implement a scheduling mechanism (e.g., `APScheduler` within the Python app, or system cron/Task Scheduler).
        *   Configure the job to run `main.py` periodically.
    2.  **Enhanced Logging:**
        *   Implement comprehensive logging across all modules using the `logging` library.
        *   Log to both console and a file (`logs/app.log`).
        *   Include timestamps, log levels, and module names.
    3.  **Advanced Error Handling & Notifications:**
        *   Implement robust error handling for file parsing, API calls, and database operations.
        *   Set up a basic notification system (e.g., email to admin) for critical failures.

**Phase 4: Refinement, Testing, and Deployment Preparation**
*   **Objective:** Ensure the system is stable, well-tested, and ready for deployment.
*   **Tasks:**
    1.  **End-to-End Testing:**
        *   Perform thorough testing of the entire workflow with various sample emails and file variations.
        *   Test edge cases (e.g., empty ZIP, missing files in ZIP, malformed CSV).
    2.  **Code Review and Refactoring:**
        *   Review code for clarity, efficiency, and adherence to best practices.
        *   Refactor as needed.
    3.  **Documentation:**
        *   Finalize README with setup, configuration, and usage instructions.
        *   Ensure comments in code are adequate.
    4.  **Deployment Package:**
        *   Prepare the application for deployment (e.g., containerization with Docker, or a simple packaged script with dependencies).

### 3. Points for Clarification (To revisit during development)
*   Confirm the exact meaning of "TRANS ITEM" in the CSV.
*   Clarify if `E-TAX_INVOICE_CARD_...PDF` requires any data extraction or is purely for archival.

This phased approach allows for building and testing the core functionality first, reducing risks and allowing for iterative improvements. 