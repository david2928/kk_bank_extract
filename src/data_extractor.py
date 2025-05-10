# Placeholder for data extraction functions (CSV) 

import pandas as pd
import logging
import os
import re
from datetime import datetime
import io # Added import

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_csv_data(csv_path, merchant_id="N/A", report_date="N/A", process_date_arg="N/A", report_source_type="UNKNOWN"):
    """
    Extracts data from the K-Merchant TAX_SUMMARY_BY_TAX_ID_CSV file.

    Args:
        csv_path (str): The path to the CSV file.
        merchant_id (str): The merchant ID, typically extracted from filename or email subject.
        report_date (str): The report date (e.g., YYYY-MM-DD), extracted from filename or email.
        process_date_arg (str): The process date passed as an argument (e.g., YYYY-MM-DD). 
                                For K-Merchant ZIPs, this is typically same as report_date.
                                This is distinct from the 'PROCESS DATE' column within the CSV.
        report_source_type (str): Identifier for the source of the report (e.g., KMERCHANT_ZIP).

    Returns:
        list: A list of dictionaries, where each dictionary represents a row of extracted data
              ready for Supabase insertion. Returns an empty list if processing fails.
    """
    if not os.path.exists(csv_path):
        logging.error(f"CSV file not found: {csv_path}")
        return []

    try:
        # The CSV seems to have a header that might span multiple rows or have non-data rows at the top.
        # We need to find the actual data table. From the image, the headers are on one row.
        # Let's try to read and then inspect. Often, these files might have an empty line or two before the header.
        # We'll assume the first row with a recognizable header like 'PROCESS DATE' is the start.
        
        # A more robust way might be to skip rows until a known header is found, 
        # but pandas read_csv is often smart enough if the header is reasonably clean.
        df = pd.read_csv(csv_path, encoding='utf-8') # Or try 'latin1' or 'cp874' for Thai characters if UTF-8 fails

        # Normalize column names: lowercase and replace spaces with underscores
        df.columns = df.columns.str.lower().str.replace(' ', '_').str.replace('/', '_')
        df.columns = df.columns.str.lower().str.replace('.', '_', regex=False) # for net.debit_amt etc.

        logging.info(f"CSV Columns after normalization: {df.columns.tolist()}")

        # Adjusted mapping based on actual CSV output
        column_mapping = {
            'process_date': 'process_date',
            'trans_item': 'trans__item',  # Adjusted from trans_item
            'total_amt': 'total_amt',
            'total_fee_commission_amount': 'total_fee_commission_amount',
            'vat': 'vat_7%',  # Adjusted from vat
            'net_debit_amt': 'debit_amt', # Adjusted from net_debit_amt
            'net_credit_amt': 'net_credit_amt',
            'wht_tax': 'w_h__tax', # Adjusted from wht_tax
            'settlement_account_currency': 'settlement_account_currency',
            'wht_code': 'vat_code' # Assuming 'vat_code' from CSV might be 'wht_code' as per data model, or it's genuinely different
        }

        # Check for required columns based on the *values* in our mapping that are expected in the CSV
        expected_csv_columns = [column_mapping[key] for key in [
            'process_date', 'trans_item', 'total_amt', 'total_fee_commission_amount',
            'vat', 'net_debit_amt', 'net_credit_amt', 'wht_tax', 'settlement_account_currency'
        ]]
        
        # 'wht_code' is handled more flexibly as it might map to 'vat_code' or be absent
        if column_mapping['wht_code'] in df.columns:
            pass # It's present, good.
        elif 'wht_code' not in column_mapping.values() and 'vat_code' not in df.columns and 'wht_code' in column_mapping : # if wht_code was a target and not found and vat_code not found.
            logging.warning(f"Column for WHT Code (expected as '{column_mapping['wht_code']}' or similar) not found in CSV.")


        missing_cols = [col for col in expected_csv_columns if col not in df.columns]
        if missing_cols:
            logging.error(f"Missing required columns in CSV {csv_path}: {missing_cols}. Available columns: {df.columns.tolist()}")
            return []

        extracted_records = []
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            
            record = {
                'merchant_id': merchant_id,
                'report_date': report_date,
                'process_date': pd.to_datetime(row[column_mapping['process_date']], dayfirst=True, errors='coerce').strftime('%Y-%m-%d') if pd.notna(row[column_mapping['process_date']]) else None,
                'trans_item_description': str(row[column_mapping['trans_item']]) if pd.notna(row[column_mapping['trans_item']]) else None,
                'total_amount': safe_float(row[column_mapping['total_amt']]),
                'total_fee_commission_amount': safe_float(row[column_mapping['total_fee_commission_amount']]),
                'vat_on_fee_amount': safe_float(row[column_mapping['vat']]),
                'net_debit_amount': safe_float(row[column_mapping['net_debit_amt']]),
                'net_credit_amount': safe_float(row[column_mapping['net_credit_amt']]),
                'wht_tax_amount': safe_float(row[column_mapping['wht_tax']]),
                'wht_code': str(row[column_mapping['wht_code']]) if column_mapping['wht_code'] in df.columns and pd.notna(row[column_mapping['wht_code']]) else None,
                'settlement_currency': str(row[column_mapping['settlement_account_currency']]) if pd.notna(row[column_mapping['settlement_account_currency']]) else None,
                'source_csv_filename': os.path.basename(csv_path),
                'report_source_type': report_source_type
            }
            
            # Only add record if process_date from CSV content is valid, as it's a key field
            if record['process_date']:
                extracted_records.append(record)
            else:
                logging.warning(f"Skipping row {index+2} due to invalid or missing process_date in {csv_path}")

        logging.info(f"Successfully extracted {len(extracted_records)} records from {csv_path}")
        return extracted_records

    except pd.errors.EmptyDataError:
        logging.error(f"CSV file is empty: {csv_path}")
        return []
    except FileNotFoundError:
        logging.error(f"CSV file not found during pandas read: {csv_path}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred during CSV processing for {csv_path}: {e}")
        logging.error(f"Columns at time of error: {df.columns.tolist() if 'df' in locals() else 'DataFrame not loaded'}")
        return []

def parse_date_from_string(date_str, date_formats=["%d/%m/%Y"]):
    """Helper to parse date string with multiple formats."""
    if not date_str: return None
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            continue
    logging.warning(f"Could not parse date: {date_str} with formats {date_formats}")
    return None

def safe_float(value, default=0.0):
    """Helper to safely convert to float."""
    if value is None: return default
    try:
        # Remove commas and strip potential extraneous characters like trailing '-'
        cleaned_value = str(value).replace(',', '').strip()
        if cleaned_value.endswith('-'):
            cleaned_value = cleaned_value[:-1].strip()
        if not cleaned_value: # Handle cases where it becomes empty after stripping, e.g. was just "-"
            return default
        return float(cleaned_value)
    except ValueError:
        return default

def safe_int(value, default=0):
    """Helper to safely convert to int."""
    if value is None: return default
    try:
        return int(str(value).replace(',', ''))
    except ValueError:
        return default

if __name__ == '__main__':
    # For direct testing of this module
    # Create a dummy CSV file named 'sample_tax_summary.csv' in the same directory as this script
    # with content similar to the K-Merchant CSV structure.
    sample_csv_path = 'sample_tax_summary.csv'
    if not os.path.exists(sample_csv_path):
        # Example CSV content based on the image (ensure actual file uses this or similar structure)
        csv_content = (
            "PROCESS DATE,TRANS ITEM,CREDIT CARD AMOUNT,QR PAYMENT CARD AMOUNT,TOTAL AMT,CREDIT CARD FEE/COMMISSION AMOUNT,QR PAYMENT FEE/COMMISSION AMOUNT,TOTAL FEE/COMMISSION AMOUNT,VAT,NET DEBIT AMT,WHT TAX,NET CREDIT AMT,SETTLEMENT ACCOUNT CURRENCY,EXCHANGE RATE,REIMBURSEMENT TRN\n"
            "08/05/2025,6,7280,0,7280,184.55,0,184.55,12.92,202.47,5.54,7082.53,THB,1,1\n"
            "08/05/2025,6,7280,0,7280,184.55,0,184.55,12.92,202.47,5.54,7082.53,THB,1,1\n"
        )
        with open(sample_csv_path, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        logging.info(f"Created dummy {sample_csv_path} for testing.")

    if os.path.exists(sample_csv_path):
        logging.info(f"Testing CSV extraction from: {sample_csv_path}")
        # merchant_id and report_date would normally be derived from the ZIP filename or email
        extracted_data = extract_csv_data(sample_csv_path, merchant_id="test_merchant_123", report_date="2025-05-21")
        if extracted_data:
            print("Extracted CSV Data:")
            for row in extracted_data:
                print(row)
        else:
            print("No data extracted or extraction failed.")
        # os.remove(sample_csv_path) # Clean up dummy file
    else:
        print(f"Skipping CSV extraction test: {sample_csv_path} not found.") 

    # PDF Testing - Requires a sample PDF named 'sample_summary_report.pdf'
    # You need to provide this file manually for testing.
    # sample_pdf_path = 'sample_summary_report.pdf' 
    # if pdfplumber and os.path.exists(sample_pdf_path):
    #     logging.info(f"Testing PDF extraction from: {sample_pdf_path}")
    #     pdf_data = extract_pdf_data(sample_pdf_path, file_merchant_id="pdf_test_merchant", file_report_date="2025-05-21")
    #     if pdf_data:
    #         print("Extracted PDF Data:")
    #         for row in pdf_data:
    #             print(row)
    #     else:
    #         print("No data extracted from PDF or extraction failed.")
    # elif pdfplumber:
    #     print(f"Skipping PDF extraction test: {sample_pdf_path} not found. Please create it for testing.")
    # else:
    #     print("Skipping PDF extraction test: pdfplumber library not installed.") 