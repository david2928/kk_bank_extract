# Placeholder for database loading functions 

import logging
import os
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Supabase client
supabase_client: Client = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logging.info("Supabase client initialized successfully.")
    else:
        logging.warning("SupABASE_URL or SUPABASE_KEY is not set. Supabase client not initialized.")
except Exception as e:
    logging.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
    supabase_client = None # Ensure it's None if initialization fails

def get_supabase_client():
    """Returns the initialized Supabase client."""
    if not supabase_client:
        logging.error("Supabase client is not initialized. Cannot perform database operations.")
    return supabase_client

def load_data_to_supabase(table_name: str, data_list: list, conflict_columns: list = None):
    """
    Loads a list of dictionaries into the specified Supabase table.

    Args:
        table_name (str): The name of the Supabase table.
        data_list (list): A list of dictionaries, where each dictionary represents a row.
        conflict_columns (list, optional): A list of column names to use for ON CONFLICT 
                                         clause in an upsert operation. If None, a simple insert is performed.

    Returns:
        tuple: (success_count, failure_count)
    """
    client = get_supabase_client()
    if not client:
        return 0, len(data_list)
    
    if not data_list:
        logging.info(f"No data provided to load into table '{table_name}'.")
        return 0, 0

    success_count = 0
    failure_count = 0

    try:
        # Supabase client's insert method can handle a list of dicts directly.
        # For upsert, ensure your Supabase table has the appropriate unique constraints defined on conflict_columns.
        if conflict_columns:
            # The python client upsert method implicitly uses the primary key for conflict
            # or you can define unique constraints on the table and use `ignore_duplicates=False` 
            # with `on_conflict` (though `on_conflict` parameter for specific columns is more SQL-like and might not be directly supported this way).
            # A common pattern for upsert on specific columns is to ensure those columns form a UNIQUE constraint in the DB.
            # The `upsert` method in supabase-py v1.x and v2.x defaults to using the primary key for conflict resolution
            # or it can update if a unique constraint is met. For specific `ON CONFLICT (col1, col2) DO UPDATE` type behavior,
            # it's often managed by the table's unique constraints.
            # We'll use `upsert=True` which generally means insert or update on conflict based on PK or unique constraints.
            response = client.table(table_name).upsert(data_list, on_conflict=",".join(conflict_columns) if isinstance(conflict_columns, list) else conflict_columns).execute()
        else:
            response = client.table(table_name).insert(data_list).execute()
        
        # `execute()` returns an APIResponse object. We need to check its data.
        # For bulk operations, the response might not directly give individual success/failure for each item
        # in the same way as some other ORMs. It usually indicates overall success or failure of the batch.
        # If there's an error in the batch, `response.data` might be empty or `response.error` will be set.
        
        if hasattr(response, 'data') and response.data: # Check if data exists and is not empty
            # For insert/upsert, response.data is usually a list of the inserted/updated records
            success_count = len(response.data)
            if success_count == len(data_list):
                logging.info(f"Successfully loaded {success_count} records into '{table_name}'.")
            else:
                # This part is tricky as Supabase bulk insert might not return partial success info easily.
                # It often succeeds or fails as a whole batch for typical RLS pass/fail.
                # If PostgREST error occurs (e.g. constraint violation not covered by upsert), response.error is set.
                logging.warning(f"Loaded {success_count} records into '{table_name}', but expected {len(data_list)}. Check for potential issues or partial batch processing.")
                # We assume if response.data is present, those were successful.
                failure_count = len(data_list) - success_count
        elif hasattr(response, 'error') and response.error:
            logging.error(f"Error loading data into '{table_name}': {response.error}")
            failure_count = len(data_list)
        else:
            # This case might occur if the operation was acknowledged but returned no data (e.g. an update that affected 0 rows but didn't error)
            # or if the response structure is unexpected.
            logging.warning(f"Data loading into '{table_name}' completed, but response data is empty or error status is unclear. Response: {response}")
            # Assuming failure if no clear success data
            failure_count = len(data_list) 
            
    except Exception as e:
        logging.error(f"Exception during data load to '{table_name}': {e}", exc_info=True)
        failure_count = len(data_list)
        success_count = 0 # Ensure success_count is 0 on exception

    return success_count, failure_count


def _deduplicate_records(data_list: list, unique_keys: list):
    """
    Deduplicates records based on the specified unique keys.
    
    Args:
        data_list (list): List of dictionaries representing records.
        unique_keys (list): List of keys that form the unique constraint.
        
    Returns:
        list: Deduplicated list of records. If duplicates exist, the last occurrence is kept.
    """
    if not data_list or not unique_keys:
        return data_list
    
    # Use a dictionary to track unique records by their unique key combination
    unique_records = {}
    
    for record in data_list:
        # Create a tuple of values for the unique keys to use as a dictionary key
        unique_key_values = tuple(record.get(key) for key in unique_keys)
        
        # Store the record, overwriting any previous record with the same unique key
        # This keeps the last occurrence of duplicate records
        unique_records[unique_key_values] = record
    
    # Return the deduplicated records as a list
    deduplicated_list = list(unique_records.values())
    
    return deduplicated_list


# Specific functions for each table (optional, but can be convenient)
def load_merchant_transaction_summaries(data_list: list):
    """Loads data into the merchant_transaction_summaries table."""
    # Updated Unique Constraint: (`merchant_id`, `report_date`, `process_date`, `tax_invoice_no`)
    # This ensures records with different tax invoice numbers are treated as separate records
    conflict_cols = ['merchant_id', 'report_date', 'process_date', 'tax_invoice_no'] 
    
    # Deduplicate records to prevent "ON CONFLICT DO UPDATE command cannot affect row a second time" error
    deduplicated_data = _deduplicate_records(data_list, conflict_cols)
    if len(deduplicated_data) < len(data_list):
        logging.warning(f"Deduplicated {len(data_list) - len(deduplicated_data)} duplicate records before loading to merchant_transaction_summaries. Original: {len(data_list)}, Deduplicated: {len(deduplicated_data)}")
    
    return load_data_to_supabase(
        table_name="merchant_transaction_summaries", 
        data_list=deduplicated_data,
        conflict_columns=conflict_cols
    )

# def load_merchant_payment_type_details(data_list: list):
#     """Loads data into the merchant_payment_type_details table."""
#     # UPDATED Unique Constraint based on user request: (`source_pdf_filename`, `payment_type`)
#     conflict_cols = ['source_pdf_filename', 'payment_type']
#     return load_data_to_supabase(
#         table_name="merchant_payment_type_details", 
#         data_list=data_list,
#         conflict_columns=conflict_cols
#     )

if __name__ == '__main__':
    # Example Usage (Requires Supabase to be set up and .env file configured)
    logging.info("db_loader.py executed directly for testing.")
    if not supabase_client:
        logging.error("Supabase client not available. Aborting test.")
    else:
        # Test data for merchant_transaction_summaries
        test_summary_data = [
            {
                'merchant_id': 'test_merchant_001', 'report_date': '2024-05-21', 'process_date': '2024-05-20',
                'trans_item_description': 'Type A', 'total_amount': 100.00, 'total_fee_commission_amount': 5.00,
                'vat_on_fee_amount': 0.35, 'net_debit_amount': 0.0, 'net_credit_amount': 94.65, 'wht_tax_amount': 0.0,
                'settlement_currency': 'THB', 'source_csv_filename': 'test1.csv'
            },
            {
                'merchant_id': 'test_merchant_001', 'report_date': '2024-05-21', 'process_date': '2024-05-21', # Different process_date
                'trans_item_description': 'Type B', 'total_amount': 200.00, 'total_fee_commission_amount': 10.00,
                'vat_on_fee_amount': 0.70, 'net_debit_amount': 0.0, 'net_credit_amount': 189.30, 'wht_tax_amount': 0.0,
                'settlement_currency': 'THB', 'source_csv_filename': 'test1.csv'
            }
        ]
        logging.info(f"Attempting to load {len(test_summary_data)} records into merchant_transaction_summaries.")
        s_summary, f_summary = load_merchant_transaction_summaries(test_summary_data)
        logging.info(f"Transaction Summaries - Success: {s_summary}, Failures: {f_summary}")

        # Test data for merchant_payment_type_details
        # test_detail_data = [
        #     {
        #         'merchant_id': 'test_merchant_001', 'report_date': '2024-05-21', 'posting_date': '2024-05-20', 'settlement_date': '2024-05-20',
        #         'channel': 'EDC', 'service': 'FULLPAY', 'payment_type': 'VISA', 'num_transactions': 5,
        #         'thb_amount': 500.00, 'commission_rate_text': '2.0%', 'commission_amount': 10.00,
        #         'vat_amount': 0.70, 'net_amount': 489.30, 'source_pdf_filename': 'test_report.pdf'
        #     }
        # ]
        # logging.info(f"Attempting to load {len(test_detail_data)} records into merchant_payment_type_details.")
        # s_detail, f_detail = load_merchant_payment_type_details(test_detail_data)
        # logging.info(f"Payment Type Details - Success: {s_detail}, Failures: {f_detail}")

        # To test upsert, run again. Counts should indicate successful upsert (usually still counts as a success by client)
        # but no new rows if the conflicting data is identical, or updated rows if some non-conflict-key data changed.
        logging.info("Attempting to load same summary data again (testing upsert)...")
        s_summary_upsert, f_summary_upsert = load_merchant_transaction_summaries(test_summary_data)
        logging.info(f"Transaction Summaries (upsert) - Success: {s_summary_upsert}, Failures: {f_summary_upsert}")

        logging.info("Test completed. Check your Supabase table for results.") 