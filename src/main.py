# Placeholder for main application logic 

import os
# import argparse # No longer needed as we are not parsing CLI args for a single zip
import logging # Retained for derive_info_from_zip_filename if it uses it
import tempfile
import shutil
import re
import traceback # For detailed error logging
from datetime import datetime
# from logging.handlers import RotatingFileHandler # Removed for file logging

# Import the config module itself
from src import config 
from src.zip_processor import extract_zip
from src.data_extractor import extract_csv_data # Removed extract_pdf_data
from src.db_loader import load_merchant_transaction_summaries # Removed load_merchant_payment_type_details
from src import email_handler
from src import gdrive_handler # Added for Google Drive operations

# Configure basic logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

# --- P3-TASK-002: Enhanced Logging Setup --- >> MODIFIED TO REMOVE FILE LOGGING
# LOG_DIR = os.path.join(config.PROJECT_ROOT, "logs")
# if not os.path.exists(LOG_DIR):
#     os.makedirs(LOG_DIR)
# LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

# Get the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO) # Set the root logger level

# Define a standard log format
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

# Configure Console Handler (streams to stdout/stderr)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# Configure Rotating File Handler -- REMOVED
# # Rotates log file when it reaches 1MB, keeps 5 backup logs
# file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=1024*1024, backupCount=5, encoding='utf-8')
# file_handler.setFormatter(log_formatter)
# logger.addHandler(file_handler)
# --- End P3-TASK-002 --- 

# (P2-TASK-003 Placeholder) Define base path for archiving processed reports
# This should ideally come from config or be a well-defined subdirectory
PROCESSED_REPORTS_ARCHIVE_BASE = os.path.join(config.PROJECT_ROOT, "processed_data", "reports")

def derive_info_from_zip_filename(zip_filename):
    """
    Derives merchant_id and report_date from a ZIP filename like:
    401016061365001_Card_20250508.zip
    E-TAX_INVOICE_CARD_401016061365001_080525E00018456_20250508.PDF (example, not a zip)
    KB1P554V2_SUM_401016061365001_20250508.pdf (example, not a zip)
    TAX_SUMMARY_BY_TAX_ID_CSV_0105566207013_20250508.csv (example, not a zip)
    
    Returns: (merchant_id, report_date_str YYYY-MM-DD) or (None, None)
    """
    base_name = os.path.basename(zip_filename)
    # Pattern for typical card report ZIP: 401016061365001_Card_20250508.zip
    match = re.match(r"(\d+)_Card_(\d{8})\.zip", base_name, re.IGNORECASE)
    if match:
        merchant_id = match.group(1)
        date_str = match.group(2)
        try:
            report_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
            return merchant_id, report_date
        except ValueError:
            logging.warning(f"Warning: Could not parse date from ZIP filename: {base_name} using primary pattern.")
            return merchant_id, None
    else:
        # Fallback for other potential naming if the primary one fails
        # Attempt to find a long number as merchant ID and a date string
        parts = base_name.replace('.zip', '').split('_')
        merchant_id_cand = None
        date_str_cand = None
        for part in parts:
            if len(part) > 10 and part.isdigit(): # Likely a merchant ID
                merchant_id_cand = part
            if len(part) == 8 and part.isdigit(): # Could be YYYYMMDD
                date_str_cand = part
            elif len(part) == 6 and part.isdigit(): # Could be YYMMDD (need to infer century)
                 try:
                    # Assuming 20xx century. This might need adjustment based on actual date ranges.
                    year = int("20" + part[:2])
                    month = int(part[2:4])
                    day = int(part[4:6])
                    date_str_cand = datetime(year,month,day).strftime("%Y%m%d")
                 except ValueError:
                    pass # Not a valid YYMMDD
        
        if merchant_id_cand and date_str_cand:
            try:
                report_date = datetime.strptime(date_str_cand, "%Y%m%d").strftime("%Y-%m-%d")
                return merchant_id_cand, report_date
            except ValueError:
                 logging.warning(f"Warning: Fallback could not parse date from ZIP filename: {base_name}")
                 return merchant_id_cand, None

    logging.warning(f"Warning: Could not derive merchant_id and report_date from ZIP filename: {base_name}")
    return None, None

def process_single_zip(zip_path, original_filename, merchant_id_from_email=None, report_date_from_email=None):
    """
    Processes a single downloaded ZIP file: extracts, parses, and loads data.
    Returns True if processing was successful, False otherwise.
    """
    logging.info(f"Processing ZIP: {original_filename} (path: {zip_path})")
    temp_extract_dir = tempfile.mkdtemp(prefix="kbank_extract_")
    all_extracted_files = [] # To keep track for archival
    try:
        extracted_file_paths = extract_zip(zip_path, temp_extract_dir)
        all_extracted_files.extend(extracted_file_paths)

        if not extracted_file_paths:
            logging.warning(f"No files extracted from {original_filename}. Skipping.")
            return False

        # --- (P2-TASK-003 File Dispatcher & Organizer - Part 1: Identify files) ---
        # TODO: Implement robust file identification based on patterns from DESIGN_DOCUMENT.md
        # For now, try to find the first CSV and PDF, assuming they are the correct ones.
        csv_file_path = next((f for f in extracted_file_paths if f.lower().endswith(".csv") and "tax_summary_by_tax_id_csv" in os.path.basename(f).lower()), None)
        # pdf_file_path = next((f for f in extracted_file_paths if f.lower().endswith(".pdf") and "kb1p554v2_sum" in os.path.basename(f).lower()), None)
        # We might also want to identify the E-TAX_INVOICE_CARD PDF for archival
        # etax_invoice_pdf_path = next((f for f in extracted_file_paths if f.lower().endswith(".pdf") and "E-TAX_INVOICE_CARD" in os.path.basename(f)), None)

        # Extract merchant_id and report_date from filename (if not available from email)
        # This is a simplified version; P2-TASK-003 will make this more robust.
        # Use the locally defined derive_info_from_zip_filename
        merchant_id, report_date_str = derive_info_from_zip_filename(original_filename)
        # If parse_zip_filename is preferred and in zip_processor, it should be:
        # from src.zip_processor import parse_zip_filename
        # merchant_id, report_date_str = parse_zip_filename(original_filename)

        # Override with email info if available (though email subject parsing is a TODO)
        merchant_id = merchant_id_from_email or merchant_id
        report_date_str = report_date_from_email or report_date_str

        if not merchant_id or not report_date_str:
            logging.error(f"Could not determine merchant_id or report_date for {original_filename}. Required for processing and archival. Skipping.")
            return False
        # --- End P2-TASK-003 Part 1 ---

        logging.info(f"Processing for Merchant ID: {merchant_id}, Report Date: {report_date_str}")

        # Initialize flags for processing results
        csv_found = False
        # pdf_found = False
        csv_load_successful = False
        # pdf_load_successful = False

        if csv_file_path:
            csv_found = True
            logging.info(f"Processing CSV: {os.path.basename(csv_file_path)}")
            csv_data_list = extract_csv_data(csv_file_path, merchant_id, report_date_str)
            if csv_data_list:
                s_count, f_count = load_merchant_transaction_summaries(csv_data_list) 
                logging.info(f"Loaded {s_count} records (failed: {f_count}) from CSV {os.path.basename(csv_file_path)}.")
                if s_count > 0 and f_count == 0: csv_load_successful = True
                elif s_count == 0 and f_count > 0 : logging.error(f"All records failed to load from CSV: {os.path.basename(csv_file_path)}")
                elif f_count > 0 : logging.warning(f"Some records failed to load from CSV: {os.path.basename(csv_file_path)}")
            else:
                logging.warning(f"No data extracted from CSV: {os.path.basename(csv_file_path)}")
        else:
            logging.info(f"No TAX_SUMMARY_BY_TAX_ID_CSV file found in {original_filename}.")

        # if pdf_file_path:
        #     pdf_found = True
        #     logging.info(f"Processing PDF: {os.path.basename(pdf_file_path)}")
        #     pdf_data_list = extract_pdf_data(pdf_file_path, merchant_id, report_date_str) 
        #     if pdf_data_list:
        #         s_count, f_count = load_merchant_payment_type_details(pdf_data_list) 
        #         logging.info(f"Loaded {s_count} records (failed: {f_count}) from PDF {os.path.basename(pdf_file_path)}.")
        #         if s_count > 0 and f_count == 0: pdf_load_successful = True
        #         elif s_count == 0 and f_count > 0 : logging.error(f"All records failed to load from PDF: {os.path.basename(pdf_file_path)}")
        #         elif f_count > 0 : logging.warning(f"Some records failed to load from PDF: {os.path.basename(pdf_file_path)}")
        #     else:
        #         logging.warning(f"No data extracted from PDF: {os.path.basename(pdf_file_path)}")
        # else:
        #     logging.info(f"No KB1P554V2_SUM PDF file found in {original_filename}.")
        
        # --- Local Archival (P2-TASK-003) ---  >> REMOVED
        # Local archival steps are being removed. Files will be uploaded directly
        # from their download/temp locations to Google Drive.
        logging.info("Skipping local archival. Files will be uploaded directly to Google Drive.")
        # --- End Local Archival ---

        # --- Google Drive Upload ---
        gdrive_upload_successful = False
        try:
            gdrive_service = gdrive_handler.get_gdrive_service()
            if gdrive_service:
                # Create folder structure: Year / Month (YYYYMM) / Date (YYYY-MM-DD)
                report_datetime = datetime.strptime(report_date_str, "%Y-%m-%d")
                year_str = report_datetime.strftime("%Y")
                month_str = report_datetime.strftime("%Y%m") # YYYYMM format for month folder
                day_str = report_date_str # YYYY-MM-DD for day folder

                year_folder_id = gdrive_handler.find_or_create_folder(gdrive_service, config.GDRIVE_ROOT_FOLDER_ID, year_str)
                if year_folder_id:
                    month_folder_id = gdrive_handler.find_or_create_folder(gdrive_service, year_folder_id, month_str)
                    if month_folder_id:
                        day_folder_id = gdrive_handler.find_or_create_folder(gdrive_service, month_folder_id, day_str)
                        if day_folder_id:
                            logging.info(f"Ensured Google Drive folder structure: {year_str}/{month_str}/{day_str} (ID: {day_folder_id})")
                            
                            files_uploaded_to_gdrive = 0
                            # Upload original ZIP (from its original download path)
                            if os.path.exists(zip_path): # zip_path is the original downloaded path
                                if gdrive_handler.upload_file_to_gdrive(gdrive_service, zip_path, day_folder_id, remote_filename=original_filename):
                                    files_uploaded_to_gdrive += 1
                            else:
                                logging.warning(f"Original ZIP file {zip_path} not found for GDrive upload.")

                            # Upload all extracted files (from the temporary extraction directory)
                            for extracted_file_path in all_extracted_files: # all_extracted_files contains paths in temp_extract_dir
                                if os.path.exists(extracted_file_path):
                                    if gdrive_handler.upload_file_to_gdrive(gdrive_service, extracted_file_path, day_folder_id):
                                        files_uploaded_to_gdrive += 1
                                else:
                                    logging.warning(f"Extracted file {extracted_file_path} not found in temp directory for GDrive upload.")
                            
                            if files_uploaded_to_gdrive > 0:
                                gdrive_upload_successful = True
                                logging.info(f"Successfully uploaded {files_uploaded_to_gdrive} file(s) to Google Drive folder: {year_str}/{month_str}/{day_str}")
                            else:
                                logging.warning(f"No files were successfully uploaded to Google Drive for report {original_filename}.")

                        else:
                            logging.error(f"Failed to create/find Google Drive Day folder: {day_str}")
                    else:
                        logging.error(f"Failed to create/find Google Drive Month folder: {month_str}")
                else:
                    logging.error(f"Failed to create/find Google Drive Year folder: {year_str}")
            else:
                logging.error("Failed to get Google Drive service. Skipping GDrive upload.")
        except Exception as gd_ex:
            logging.error(f"An exception occurred during Google Drive operations for {original_filename}: {gd_ex}", exc_info=True)
            gdrive_upload_successful = False # Ensure it's marked as failed
        # --- End Google Drive Upload ---

        # Determine overall processing success for this ZIP
        if not csv_found: # and not pdf_found:
            logging.warning(f"No CSV key files were found in {original_filename}. Processing considered failed.")
            return False # Failed if no key files identified
        
        # If a key file was expected (found), its data loading must have been successful.
        processing_successful_final = True
        if csv_found and not csv_load_successful:
            processing_successful_final = False
            logging.warning(f"CSV file found for {original_filename} but data loading was not successful.")
        # if pdf_found and not pdf_load_successful:
        #     processing_successful_final = False
        #     logging.warning(f"PDF file found for {original_filename} but data loading was not successful.")

        if processing_successful_final and gdrive_upload_successful:
            logging.info(f"All found key CSV reports in {original_filename} processed, loaded to Supabase, and archived to Google Drive successfully.")
        elif processing_successful_final and not gdrive_upload_successful:
            logging.warning(f"CSV data for {original_filename} processed and loaded to Supabase, but Google Drive archival failed or was incomplete.")
            # Still consider processing_successful_final = True for Supabase part, but email label might need adjustment
        else:
            logging.warning(f"One or more key CSV reports in {original_filename} had issues with data extraction, Supabase loading, or GDrive archival.")
            
        # Final success depends on both Supabase load and GDrive upload for this new requirement
        return processing_successful_final and gdrive_upload_successful

    except Exception as e:
        logging.error(f"ERROR processing ZIP file {original_filename} (path: {zip_path}): {e}")
        logging.error(traceback.format_exc()) # Log full traceback
        return False
    finally:
        # Clean up temporary extraction directory
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
            logging.info(f"Cleaned up temporary directory: {temp_extract_dir}")

def main():
    logging.info("Starting K-Merchant Email Report Processing System...")

    # Initialize Gmail Service
    logging.info("Initializing Gmail service...")
    gmail_service = email_handler.get_gmail_service()

    if not gmail_service:
        logging.error("Failed to initialize Gmail service. Exiting.")
        return
    logging.info("Gmail service initialized successfully.")

    # User requested to change search query to 7 days for quicker testing
    # Temporarily removing 'is:unread' to process all matching emails for testing PDF parser
    # search_query = 'subject:("K-Merchant Reports as of") has:attachment newer_than:7d' 
    # Updated search query to use the LABEL_PROCESSED constant and exclude already processed emails
    search_query = f'subject:("K-Merchant Reports as of") has:attachment -label:{email_handler.LABEL_PROCESSED}'
    logging.info(f"Using email search query: {search_query}")

    downloaded_report_infos = email_handler.fetch_new_reports(
        gmail_service,
        search_query,
        config.DOWNLOAD_REPORTS_DIR
    )

    if not downloaded_report_infos:
        logging.info("No new reports found or downloaded. Exiting.")
        return

    logging.info(f"Fetched {len(downloaded_report_infos)} new report(s).")
    successful_processing_count = 0
    failed_processing_count = 0

    for report_info in downloaded_report_infos:
        message_id = report_info['message_id']
        zip_file_path = report_info['zip_path']
        original_zip_filename = report_info['original_filename']

        logging.info(f"\n--- Processing report from Message ID: {message_id}, File: {original_zip_filename} ---")
        
        # TODO: Extract merchant_id and report_date from email subject if possible
        # For now, process_single_zip will try to parse from filename
        # merchant_id_from_email, report_date_from_email = parse_email_subject(subject_of_email) 

        processing_successful = process_single_zip(
            zip_path=zip_file_path, 
            original_filename=original_zip_filename
            # merchant_id_from_email=merchant_id_from_email, # Add these when email subject parsing is ready
            # report_date_from_email=report_date_from_email
        )

        if processing_successful:
            successful_processing_count += 1
            logging.info(f"Successfully processed report from Message ID: {message_id}, File: {original_zip_filename}.")
            email_handler.add_label_to_email(gmail_service, message_id, email_handler.LABEL_PROCESSED)
            # Optionally, remove the UNREAD label if it wasn't handled by search and you want it explicitly marked read
            email_handler.mark_email_as_read(gmail_service, message_id) 
            # Optionally, if it might have failed before, remove the FAILED label
            email_handler.remove_label_from_email(gmail_service, message_id, email_handler.LABEL_FAILED)

            # Clean up the downloaded ZIP file after successful processing and archival
            try:
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
                    logging.info(f"Successfully deleted downloaded ZIP: {zip_file_path}")
                else:
                    logging.warning(f"Attempted to delete ZIP {zip_file_path}, but it was not found.")
            except OSError as e:
                logging.error(f"Error deleting ZIP file {zip_file_path}: {e}")
        else:
            failed_processing_count += 1
            logging.error(f"Failed to process report from Message ID: {message_id}, File: {original_zip_filename}.")
            email_handler.add_label_to_email(gmail_service, message_id, email_handler.LABEL_FAILED)
            # Important: Do not add PROCESSED label here. 
            # If it was previously PROCESSED and now failed (e.g. reprocessing due to code change broke something),
            # it might be an edge case. For now, we assume a failure means it's not fully processed.

    logging.info("\n--- Processing Summary ---")
    logging.info(f"Successfully processed reports: {successful_processing_count}")
    logging.info(f"Failed to process reports: {failed_processing_count}")
    logging.info("K-Merchant Email Report Processing System finished.")

if __name__ == "__main__":
    main() 