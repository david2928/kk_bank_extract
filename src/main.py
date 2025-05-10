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
import csv # Added for CSV parsing

# Import the config module itself
from src import config 
from src.zip_processor import extract_zip
from src.data_extractor import extract_csv_data # Removed extract_pdf_data
from src.db_loader import load_merchant_transaction_summaries, get_supabase_client # Added get_supabase_client
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
    Derives merchant_id and report_date from a K-Merchant ZIP filename.
    Example: 401016061365001_Card_20250508.zip -> ("401016061365001", "2025-05-08")
    Returns: (merchant_id, report_date_str YYYY-MM-DD) or (None, None)
    """
    base_name = os.path.basename(zip_filename)
    match = re.match(r"(\d+)_Card_(\d{8})\.zip", base_name, re.IGNORECASE)
    if match:
        merchant_id = match.group(1)
        date_str = match.group(2)
        try:
            report_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
            return merchant_id, report_date
        except ValueError:
            logger.warning(f"Could not parse date from ZIP filename: {base_name} using primary pattern.")
            return merchant_id, None # Return merchant_id even if date parsing fails for some reason
    else:
        # Fallback for other potential naming patterns (simplified)
        parts = base_name.replace('.zip', '').split('_')
        merchant_id_cand = None
        date_str_cand = None
        for part in parts:
            if len(part) > 10 and part.isdigit():
                merchant_id_cand = part
            if len(part) == 8 and part.isdigit():
                try:
                    # Check if it's a valid YYYYMMDD date
                    datetime.strptime(part, "%Y%m%d")
                    date_str_cand = part
                except ValueError:
                    continue # Not a YYYYMMDD date
        
        if merchant_id_cand and date_str_cand:
            try:
                report_date = datetime.strptime(date_str_cand, "%Y%m%d").strftime("%Y-%m-%d")
                return merchant_id_cand, report_date
            except ValueError:
                 logger.warning(f"Fallback could not parse valid date from ZIP filename: {base_name}")
                 return merchant_id_cand, None

    logger.warning(f"Could not derive merchant_id and report_date from ZIP filename: {base_name}")
    return None, None

def derive_info_from_ewallet_csv_filename(csv_filename):
    """
    Derives merchant_id and process_date from an eWallet CSV filename.
    Example: 401016061373001_LENGOLF_20250508.csv -> ("401016061373001", "2025-05-08")
    Returns: (merchant_id, process_date_str YYYY-MM-DD) or (None, None)
    """
    base_name = os.path.basename(csv_filename)
    parts = base_name.split('_')
    if len(parts) >= 3:
        merchant_id = parts[0]
        date_str_yyyymmdd = parts[-1].replace('.csv', '') # Takes the last part before .csv
        if merchant_id.isdigit() and date_str_yyyymmdd.isdigit() and len(date_str_yyyymmdd) == 8:
            try:
                process_date = datetime.strptime(date_str_yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")
                return merchant_id, process_date
            except ValueError:
                logger.warning(f"Could not parse date from eWallet CSV filename: {base_name}")
                return merchant_id, None # Return merchant_id if date parsing fails
        else:
             logger.warning(f"Filename format for eWallet CSV not as expected: {base_name}. Expected merchantId_name_YYYYMMDD.csv")
             return None, None # If parts are not as expected merchant ID might be wrong too
    logger.warning(f"Could not derive merchant_id and process_date from eWallet CSV filename: {base_name}")
    return None, None

def _ensure_gdrive_folder_structure(gdrive_service, report_date_str, base_folder_id):
    """Helper to create Year/Month/Day folder structure in Google Drive."""
    try:
        report_datetime = datetime.strptime(report_date_str, "%Y-%m-%d")
        year_str = report_datetime.strftime("%Y")
        month_str = report_datetime.strftime("%Y%m") 
        day_str = report_date_str 

        year_folder_id = gdrive_handler.find_or_create_folder(gdrive_service, base_folder_id, year_str)
        if year_folder_id:
            month_folder_id = gdrive_handler.find_or_create_folder(gdrive_service, year_folder_id, month_str)
            if month_folder_id:
                day_folder_id = gdrive_handler.find_or_create_folder(gdrive_service, month_folder_id, day_str)
                if day_folder_id:
                    logger.info(f"Ensured Google Drive folder structure: {year_str}/{month_str}/{day_str} (ID: {day_folder_id})")
                    return day_folder_id
                else:
                    logger.error(f"Failed to create/find Google Drive Day folder: {day_str}")
            else:
                logger.error(f"Failed to create/find Google Drive Month folder: {month_str}")
        else:
            logger.error(f"Failed to create/find Google Drive Year folder: {year_str}")
    except ValueError:
        logger.error(f"Invalid report_date_str format for GDrive folder structure: {report_date_str}. Expected YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error ensuring GDrive folder structure for date {report_date_str}: {e}", exc_info=True)
    return None

def process_single_zip(report_info, gdrive_service):
    """
    Processes a single downloaded K-Merchant ZIP file.
    Extracts, parses TAX_SUMMARY_BY_TAX_ID_CSV_..., loads to Supabase, and archives all contents to GDrive.
    """
    zip_path = report_info['zip_path']
    original_filename = report_info['original_filename']
    # message_id = report_info['message_id'] # Available if needed for finer-grained error reporting

    logging.info(f"Processing KMERCHANT_ZIP: {original_filename} (path: {zip_path})")
    temp_extract_dir = tempfile.mkdtemp(prefix="kbank_zip_extract_")
    all_extracted_files = []
    gdrive_upload_successful = False
    csv_load_successful = False
    processing_successful_overall = False

    try:
        extracted_file_paths = extract_zip(zip_path, temp_extract_dir)
        all_extracted_files.extend(extracted_file_paths)

        if not extracted_file_paths:
            logging.warning(f"No files extracted from {original_filename}. Skipping.")
            return False # Considered failure for this report

        # --- Identify key files and derive info ---
        csv_file_path = next((f for f in extracted_file_paths if f.lower().endswith(".csv") and "tax_summary_by_tax_id_csv" in os.path.basename(f).lower()), None)
        
        merchant_id, report_date_str = derive_info_from_zip_filename(original_filename)

        if not merchant_id or not report_date_str:
            logging.error(f"Could not determine merchant_id or report_date for ZIP {original_filename}. Required for processing. Skipping.")
            return False

        logging.info(f"Processing ZIP for Merchant ID: {merchant_id}, Report Date: {report_date_str}")

        # --- Process CSV data ---
        if csv_file_path:
            logging.info(f"Processing CSV from ZIP: {os.path.basename(csv_file_path)}")
            # process_date for this type of report is usually the same as report_date
            csv_data_list = extract_csv_data(csv_file_path, merchant_id, report_date_str, report_date_str, 'KMERCHANT_ZIP') 
            if csv_data_list:
                s_count, f_count = load_merchant_transaction_summaries(csv_data_list) 
                logging.info(f"Loaded {s_count} records (failed: {f_count}) from CSV {os.path.basename(csv_file_path)}.")
                if s_count > 0 and f_count == 0:
                    csv_load_successful = True
                elif s_count == 0 and f_count > 0:
                    logging.error(f"All records failed to load from CSV: {os.path.basename(csv_file_path)}")
                elif f_count > 0:
                    logging.warning(f"Some records failed to load from CSV: {os.path.basename(csv_file_path)}")
            else:
                logging.warning(f"No data extracted from CSV: {os.path.basename(csv_file_path)}")
        else:
            logging.info(f"No TAX_SUMMARY_BY_TAX_ID_CSV file found in {original_filename}. This might be an issue if one was expected.")
            # Depending on requirements, this could be a failure. For now, we proceed to GDrive upload.
            # If CSV is mandatory for a ZIP to be "successful", set csv_load_successful = False here explicitly.

        # --- Google Drive Upload ---
        if gdrive_service and report_date_str: # report_date_str needed for folder structure
            day_folder_id = _ensure_gdrive_folder_structure(gdrive_service, report_date_str, config.GDRIVE_ROOT_FOLDER_ID)
            if day_folder_id:
                files_uploaded_to_gdrive = 0
                # Upload original ZIP
                if os.path.exists(zip_path):
                    # Check and delete existing original ZIP file
                    existing_zip_id = gdrive_handler.find_file_id_by_name_in_folder(gdrive_service, day_folder_id, original_filename)
                    if existing_zip_id:
                        logger.info(f"Found existing ZIP '{original_filename}' (ID: {existing_zip_id}) in GDrive folder {day_folder_id}. Deleting it.")
                        gdrive_handler.delete_file_by_id(gdrive_service, existing_zip_id)
                    
                    if gdrive_handler.upload_file_to_gdrive(gdrive_service, zip_path, day_folder_id, remote_filename=original_filename):
                        files_uploaded_to_gdrive += 1
                # Upload all extracted files
                for extracted_file_path in all_extracted_files:
                    if os.path.exists(extracted_file_path):
                        extracted_filename = os.path.basename(extracted_file_path)
                        # Check and delete existing extracted file
                        existing_extracted_file_id = gdrive_handler.find_file_id_by_name_in_folder(gdrive_service, day_folder_id, extracted_filename)
                        if existing_extracted_file_id:
                            logger.info(f"Found existing extracted file '{extracted_filename}' (ID: {existing_extracted_file_id}) in GDrive folder {day_folder_id}. Deleting it.")
                            gdrive_handler.delete_file_by_id(gdrive_service, existing_extracted_file_id)

                        if gdrive_handler.upload_file_to_gdrive(gdrive_service, extracted_file_path, day_folder_id): # Uses original basename from extracted_file_path
                            files_uploaded_to_gdrive += 1
                
                expected_files_to_upload = len(all_extracted_files) + (1 if os.path.exists(zip_path) else 0)
                if files_uploaded_to_gdrive >= expected_files_to_upload : # Check if all expected files uploaded
                    gdrive_upload_successful = True
                    logging.info(f"Successfully uploaded all {files_uploaded_to_gdrive} associated file(s) for {original_filename} to Google Drive.")
                elif files_uploaded_to_gdrive > 0:
                     gdrive_upload_successful = True # Partial success, but still mark GDrive as successful
                     logging.warning(f"Uploaded {files_uploaded_to_gdrive} file(s) to Google Drive for {original_filename}, but some might be missing.")
                else:
                    logging.warning(f"No files were successfully uploaded to Google Drive for report {original_filename}.")
            else:
                logging.error(f"GDrive folder structure failed for {original_filename}, cannot upload.")
        elif not gdrive_service:
             logging.error("Google Drive service not available. Skipping GDrive upload.")
        elif not report_date_str:
            logging.error(f"Report date unknown for {original_filename}. Skipping GDrive upload as folder structure cannot be determined.")

        # Determine overall processing success for this ZIP
        # For KMERCHANT_ZIP, success requires CSV load (if CSV was found) and GDrive upload.
        if csv_file_path: # If a CSV was expected/found
            processing_successful_overall = csv_load_successful and gdrive_upload_successful
        else: # If no CSV was found (e.g. ZIP with only PDFs), GDrive upload is enough
            processing_successful_overall = gdrive_upload_successful
        
        return processing_successful_overall

    except Exception as e:
        logging.error(f"ERROR processing KMERCHANT_ZIP file {original_filename} (path: {zip_path}): {e}", exc_info=True)
        return False
    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
            logging.info(f"Cleaned up temporary directory: {temp_extract_dir}")

def process_ewallet_csv(report_info, gdrive_service, supabase_client):
    """
    Processes a single eWallet CSV file.
    Parses, loads to Supabase, and archives to GDrive.
    """
    csv_path = report_info['csv_path']
    original_filename = report_info['original_filename']
    # message_id = report_info['message_id'] # Available

    logging.info(f"Processing EWALLET_CSV: {original_filename} (path: {csv_path})")
    
    supabase_load_successful = False
    gdrive_upload_successful = False

    try:
        merchant_id_from_filename, process_date_str = derive_info_from_ewallet_csv_filename(original_filename)
        
        if not merchant_id_from_filename or not process_date_str:
            logging.error(f"Could not derive merchant_id or process_date from CSV filename: {original_filename}. Skipping.")
            return False

        report_date_str = None # To be extracted from H row
        data_for_supabase = None

        with open(csv_path, mode='r', encoding='utf-8-sig') as infile: # utf-8-sig for potential BOM
            reader = csv.reader(infile)
            headers = []
            try:
                headers = next(reader) # First row for headers
                logger.debug(f"eWallet CSV Headers: {headers}")
            except StopIteration:
                logging.error(f"CSV file {original_filename} is empty or has no headers.")
                return False

            for i, row in enumerate(reader):
                if not row: continue # Skip empty rows

                # Extract Report Date from H row (assuming it's the first data row after headers)
                if row[0].strip() == 'H':
                    try:
                        # Example '08/05/25' -> DD/MM/YY
                        # KBank CSV 'DATE' header has values like '08/05/25'
                        date_val_from_h = row[4].strip() # DATE is at index 4 of the header row
                        if len(date_val_from_h.split('/')) == 3 :
                             # Assuming DD/MM/YY from example '08/05/25'
                            day, month, year_short = date_val_from_h.split('/')
                            # Construct YYYY-MM-DD, assuming 20xx
                            report_date_str = f"20{year_short}-{month.zfill(2)}-{day.zfill(2)}"
                            logger.info(f"Extracted report_date: {report_date_str} from H row of {original_filename}")
                        else:
                            logger.warning(f"H row DATE format not DD/MM/YY in {original_filename}: {date_val_from_h}")
                    except IndexError:
                        logger.warning(f"Could not find DATE field in H row (index 4) for {original_filename}. Row: {row}")
                    except ValueError:
                        logger.warning(f"Could not parse DATE from H row in {original_filename}: {date_val_from_h}")


                # Find "MERCHANT TOTAL" row based on the 15th field (index 14)
                # Headers: ..., "ITEM ","COMM        ","VAT         ","NET           ","SALE          ", ...
                # Indices: ...,   14   ,     15      ,     16       ,      17      ,      18      ,      19       ...
                # Data:    ...,MERCHANT TOTAL ,1        ,19.68       ,1.38        ,1208.94       ,1230           ,...
                if len(row) > 19 and row[14].strip() == "MERCHANT TOTAL": # Ensure row has enough columns up to SALE
                    try:
                        # Corrected indices:
                        comm_str = row[16].strip() # Actual COMM is at index 16
                        vat_str = row[17].strip()  # Actual VAT is at index 17
                        net_str = row[18].strip()  # Actual NET is at index 18
                        sale_str = row[19].strip() # Actual SALE is at index 19

                        comm = float(comm_str) if comm_str else 0.0
                        vat = float(vat_str) if vat_str else 0.0
                        net = float(net_str) if net_str else 0.0
                        sale = float(sale_str) if sale_str else 0.0
                        
                        # Calculate derived financial values
                        net_debit_calc = round(comm + vat, 2)
                        wht_tax_calc = round(0.03 * comm, 2)

                        if not report_date_str: # If H row wasn't found or date couldn't be parsed
                            logger.warning(f"Report date from H row not available for {original_filename} when processing MERCHANT TOTAL. Using process_date ({process_date_str}) as fallback for report_date.")
                            report_date_str_for_db = process_date_str
                        else:
                            report_date_str_for_db = report_date_str

                        data_for_supabase = {
                            'merchant_id': merchant_id_from_filename,
                            'report_date': report_date_str_for_db,
                            'process_date': process_date_str, # From filename
                            'trans_item_description': 'EWALLET_MERCHANT_SUMMARY',
                            'total_amount': sale,
                            'total_fee_commission_amount': comm,
                            'vat_on_fee_amount': vat,
                            'net_debit_amount': net_debit_calc, 
                            'net_credit_amount': net,
                            'wht_tax_amount': wht_tax_calc,
                            'settlement_currency': 'THB',
                            'source_csv_filename': original_filename,
                            'report_source_type': 'EWALLET_CSV'
                        }
                        logger.info(f"Prepared data from MERCHANT TOTAL for {original_filename}: {data_for_supabase}")
                        break # Found the row we need
                    except (IndexError, ValueError) as ve:
                        logger.error(f"Error parsing MERCHANT TOTAL row in {original_filename}: {ve}. Row content: {row}")
                        data_for_supabase = None # Invalidate data if parsing fails
                        break
        
        if data_for_supabase and supabase_client:
            s_count, f_count = load_merchant_transaction_summaries([data_for_supabase])
            if s_count > 0:
                supabase_load_successful = True
                logger.info(f"Successfully loaded data for {original_filename} to Supabase.")
            else:
                logger.error(f"Failed to load data for {original_filename} to Supabase (Success: {s_count}, Fail: {f_count}).")
        elif not data_for_supabase:
            logger.error(f"No data extracted or MERCHANT TOTAL row not found/parsed in {original_filename}.")
        elif not supabase_client:
            logger.error("Supabase client not available. Cannot load data.")

        # --- Google Drive Upload ---
        # Use process_date_str from filename for folder structure as it's more reliable for eWallet CSVs
        # If report_date_str from H row is available, it's used for the actual report_date field in DB.
        date_for_gdrive_folder = process_date_str 
        if not date_for_gdrive_folder and report_date_str: # Fallback to H row date if filename date failed
            date_for_gdrive_folder = report_date_str
        
        if gdrive_service and date_for_gdrive_folder:
            day_folder_id = _ensure_gdrive_folder_structure(gdrive_service, date_for_gdrive_folder, config.GDRIVE_ROOT_FOLDER_ID)
            if day_folder_id:
                # Check and delete existing CSV file
                existing_csv_id = gdrive_handler.find_file_id_by_name_in_folder(gdrive_service, day_folder_id, original_filename)
                if existing_csv_id:
                    logger.info(f"Found existing eWallet CSV '{original_filename}' (ID: {existing_csv_id}) in GDrive folder {day_folder_id}. Deleting it.")
                    gdrive_handler.delete_file_by_id(gdrive_service, existing_csv_id)

                if gdrive_handler.upload_file_to_gdrive(gdrive_service, csv_path, day_folder_id, remote_filename=original_filename):
                    gdrive_upload_successful = True
                    logger.info(f"Successfully uploaded {original_filename} to Google Drive.")
                else:
                    logger.error(f"Failed to upload {original_filename} to Google Drive.")
            else:
                logger.error(f"GDrive folder structure failed for {original_filename}, cannot upload CSV.")
        elif not gdrive_service:
            logger.error("Google Drive service not available. Skipping GDrive upload for eWallet CSV.")
        elif not date_for_gdrive_folder:
             logger.error(f"Date for GDrive folder structure unknown for {original_filename}. Skipping GDrive upload.")


        return supabase_load_successful and gdrive_upload_successful

    except Exception as e:
        logger.error(f"ERROR processing EWALLET_CSV file {original_filename} (path: {csv_path}): {e}", exc_info=True)
        return False

def process_ewallet_etax_pdf(report_info, gdrive_service):
    """
    Processes a single eWallet E-TAX PDF file.
    Only archives to GDrive.
    """
    pdf_path = report_info['pdf_path']
    original_filename = report_info['original_filename']
    # message_id = report_info['message_id'] # Available

    logging.info(f"Processing EWALLET_ETAX_PDF: {original_filename} (path: {pdf_path})")
    gdrive_upload_successful = False
    
    try:
        # For E-Tax PDF, filename might not have a clear date for folder structure.
        # We might need to parse date from email subject or use email received date if available.
        # "E-TAX INVOICE FOR EWALLET 401016061373001 LENGOLF" - no date in this example subject.
        # Example filename: E-TAX_INVOICE_EWALLET_401016061373001_02022025.pdf should go to 2025/202502/2025-02-02
        
        date_for_gdrive_folder = None
        # Try to match DDMMYYYY at the end of the filename, preceded by an underscore
        match_date = re.search(r"_(\d{8})\.pdf$", original_filename, re.IGNORECASE)
        if match_date:
            date_str_ddmmyyyy = match_date.group(1)
            try:
                date_for_gdrive_folder = datetime.strptime(date_str_ddmmyyyy, "%d%m%Y").strftime("%Y-%m-%d")
                logger.info(f"Parsed date {date_for_gdrive_folder} from ETAX PDF filename: {original_filename}")
            except ValueError:
                logger.warning(f"Could not parse DDMMYYYY date string '{date_str_ddmmyyyy}' from ETAX PDF filename {original_filename}. Will use current date.")
        else:
            logger.warning(f"Date pattern not found in ETAX PDF filename {original_filename}. Will use current date.")
        
        if not date_for_gdrive_folder:
            date_for_gdrive_folder = datetime.now().strftime("%Y-%m-%d")
            logger.warning(f"Using current date {date_for_gdrive_folder} for GDrive archival folder for {original_filename}.")


        if gdrive_service and date_for_gdrive_folder:
            day_folder_id = _ensure_gdrive_folder_structure(gdrive_service, date_for_gdrive_folder, config.GDRIVE_ROOT_FOLDER_ID)
            if day_folder_id:
                # Check and delete existing PDF file
                existing_pdf_id = gdrive_handler.find_file_id_by_name_in_folder(gdrive_service, day_folder_id, original_filename)
                if existing_pdf_id:
                    logger.info(f"Found existing eWallet ETAX PDF '{original_filename}' (ID: {existing_pdf_id}) in GDrive folder {day_folder_id}. Deleting it.")
                    gdrive_handler.delete_file_by_id(gdrive_service, existing_pdf_id)
                
                if gdrive_handler.upload_file_to_gdrive(gdrive_service, pdf_path, day_folder_id, remote_filename=original_filename):
                    gdrive_upload_successful = True
                    logger.info(f"Successfully uploaded {original_filename} to Google Drive.")
                else:
                    logger.error(f"Failed to upload {original_filename} to Google Drive.")
            else:
                logger.error(f"GDrive folder structure failed for {original_filename}, cannot upload PDF.")
        elif not gdrive_service:
            logger.error("Google Drive service not available. Skipping GDrive upload for eWallet ETAX PDF.")
        elif not date_for_gdrive_folder:
             logger.error(f"Date for GDrive folder structure unknown for {original_filename}. Skipping GDrive upload.")

        return gdrive_upload_successful
    except Exception as e:
        logger.error(f"ERROR processing EWALLET_ETAX_PDF file {original_filename} (path: {pdf_path}): {e}", exc_info=True)
        return False

def main():
    logging.info("Starting K-Merchant Email Report Processing System...")

    # --- Define Report Configurations ---
    KMERCHANT_ZIP_CONFIG = {
        'search_query': 'subject:("K-Merchant Reports as of") has:attachment',
        'desired_filename_extension': ".zip",
        'report_type': "KMERCHANT_ZIP",
        'file_path_key': "zip_path",
        'processed_label': email_handler.LABEL_PROCESSED,
        'failed_label': email_handler.LABEL_FAILED
    }
    EWALLET_CSV_CONFIG = {
        'search_query': 'subject:("EWALLET REPORT") has:attachment filename:.csv',
        'desired_filename_extension': ".csv",
        'report_type': "EWALLET_CSV",
        'file_path_key': "csv_path",
        'processed_label': email_handler.LABEL_EWALLET_CSV_PROCESSED,
        'failed_label': email_handler.LABEL_FAILED 
    }
    EWALLET_ETAX_PDF_CONFIG = {
        'search_query': 'subject:("E-TAX INVOICE FOR EWALLET") has:attachment filename:.pdf',
        'desired_filename_extension': ".pdf",
        'report_type': "EWALLET_ETAX_PDF",
        'file_path_key': "pdf_path",
        'processed_label': email_handler.LABEL_EWALLET_ETAX_PDF_PROCESSED,
        'failed_label': email_handler.LABEL_FAILED
    }
    
    report_configs = [KMERCHANT_ZIP_CONFIG, EWALLET_CSV_CONFIG, EWALLET_ETAX_PDF_CONFIG]
    all_fetched_reports = []
    
    # --- Initialize Services ---
    logging.info("Initializing Gmail service...")
    gmail_service = email_handler.get_gmail_service()
    if not gmail_service:
        logging.error("Failed to initialize Gmail service. Exiting.")
        return
    logging.info("Gmail service initialized successfully.")

    logging.info("Initializing Google Drive service...")
    gdrive_service = gdrive_handler.get_gdrive_service()
    if not gdrive_service:
        logging.warning("Failed to initialize Google Drive service. GDrive operations will be skipped.")
    else:
        logging.info("Google Drive service initialized successfully.")

    logging.info("Initializing Supabase client...")
    supabase_client = get_supabase_client() # from db_loader
    if not supabase_client:
        logging.warning("Failed to initialize Supabase client. Database operations will be skipped for relevant reports.")
    else:
        logging.info("Supabase client initialized successfully.")


    # --- Fetch all types of reports ---
    for rep_config in report_configs:
        logging.info(f"Fetching reports for type: {rep_config['report_type']}...")
        try:
            fetched_items = email_handler.fetch_new_reports(
                gmail_service,
                rep_config['search_query'],
                config.DOWNLOAD_REPORTS_DIR,
                rep_config 
            )
            if fetched_items:
                all_fetched_reports.extend(fetched_items)
                logging.info(f"Fetched {len(fetched_items)} items for type: {rep_config['report_type']}.")
            else:
                logging.info(f"No new items found for type: {rep_config['report_type']}.")
        except Exception as e_fetch:
            logging.error(f"Error fetching reports for type {rep_config['report_type']}: {e_fetch}", exc_info=True)


    if not all_fetched_reports:
        logging.info("No new reports of any type found or downloaded. Exiting.")
        return

    logging.info(f"Fetched a total of {len(all_fetched_reports)} new report item(s) across all types.")
    successful_processing_count = 0
    failed_processing_count = 0

    for report_info in all_fetched_reports:
        report_type = report_info['report_type']
        message_id = report_info['message_id']
        original_filename = report_info['original_filename']
        file_path_key = None # Determine based on report_type from config
        
        current_config = next((rc for rc in report_configs if rc['report_type'] == report_type), None)
        if not current_config:
            logging.error(f"No config found for report_type {report_type} from message ID {message_id}. Skipping.")
            failed_processing_count +=1
            continue
            
        file_path_key = current_config['file_path_key']
        downloaded_file_path = report_info[file_path_key]
        
        current_processed_label = current_config['processed_label']
        current_failed_label = current_config['failed_label']
        
        processing_successful = False
        
        try:
            if report_type == "KMERCHANT_ZIP":
                if not gdrive_service: logging.warning("GDrive service unavailable for KMERCHANT_ZIP processing.")
                processing_successful = process_single_zip(report_info, gdrive_service)
            elif report_type == "EWALLET_CSV":
                if not supabase_client: logging.warning("Supabase client unavailable for EWALLET_CSV processing.")
                if not gdrive_service: logging.warning("GDrive service unavailable for EWALLET_CSV processing.")
                processing_successful = process_ewallet_csv(report_info, gdrive_service, supabase_client)
            elif report_type == "EWALLET_ETAX_PDF":
                if not gdrive_service: logging.warning("GDrive service unavailable for EWALLET_ETAX_PDF processing.")
                processing_successful = process_ewallet_etax_pdf(report_info, gdrive_service)
            else:
                logging.warning(f"Unknown report type: {report_type} for message {message_id}, file {original_filename}. Skipping.")
                processing_successful = False

            if processing_successful:
                successful_processing_count += 1
                logging.info(f"Successfully processed: {report_type} from Message ID: {message_id}, File: {original_filename}.")
                email_handler.add_label_to_email(gmail_service, message_id, current_processed_label)
                email_handler.mark_email_as_read(gmail_service, message_id) 
                email_handler.remove_label_from_email(gmail_service, message_id, current_failed_label) # Remove fail label if it was there
            else:
                failed_processing_count += 1
                logging.error(f"Failed to process: {report_type} from Message ID: {message_id}, File: {original_filename}.")
                email_handler.add_label_to_email(gmail_service, message_id, current_failed_label)
        
        except Exception as e_proc:
            failed_processing_count += 1
            logging.error(f"Unhandled exception processing {report_type} (MsgID: {message_id}, File: {original_filename}): {e_proc}", exc_info=True)
            email_handler.add_label_to_email(gmail_service, message_id, current_failed_label)


        # Clean up the downloaded file after processing attempt
        try:
            if os.path.exists(downloaded_file_path):
                os.remove(downloaded_file_path)
                logging.info(f"Successfully deleted downloaded file: {downloaded_file_path}")
            else:
                logging.warning(f"Attempted to delete file {downloaded_file_path}, but it was not found.")
        except OSError as e_del:
            logging.error(f"Error deleting file {downloaded_file_path}: {e_del}")

    logging.info("\n--- Processing Summary ---")
    logging.info(f"Total reports processed: {len(all_fetched_reports)}")
    logging.info(f"Successfully processed reports: {successful_processing_count}")
    logging.info(f"Failed to process reports: {failed_processing_count}")

if __name__ == '__main__':
    main() 