import os.path
import base64
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from . import config

# Scopes for Gmail API - adjusted for service account usage
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

logger = logging.getLogger(__name__)

# Label names
LABEL_PROCESSED = "KMERCHANT_PROCESSED"
LABEL_FAILED = "KMERCHANT_PROCESSING_FAILED"
LABEL_EWALLET_CSV_PROCESSED = "EWALLET_CSV_PROCESSED"
LABEL_EWALLET_ETAX_PDF_PROCESSED = "EWALLET_ETAX_PDF_PROCESSED"

# Default paths - these will be overridden by arguments in functions
DEFAULT_CREDENTIALS_FILE = 'credentials.json'
DEFAULT_TOKEN_FILE = 'token.json'
DEFAULT_DOWNLOAD_DIR = 'downloads'

def get_gmail_service():
    """Authenticates with Gmail API using a service account and returns the service object."""
    creds = None
    service_account_key_path = config.GOOGLE_SERVICE_ACCOUNT_KEY_PATH
    gmail_user_to_impersonate = config.GMAIL_USER_EMAIL

    if not os.path.exists(service_account_key_path):
        logger.error(f"Service account key file not found at {service_account_key_path}. "
                     f"Ensure it's correctly placed and GOOGLE_SERVICE_ACCOUNT_KEY_PATH is set.")
        return None
    
    if not gmail_user_to_impersonate:
        logger.error("GMAIL_USER_EMAIL is not set in config. Cannot impersonate user.")
        return None

    try:
        creds = Credentials.from_service_account_file(
            service_account_key_path,
            scopes=SCOPES,
            subject=gmail_user_to_impersonate # Impersonate the target user
        )
        logger.info("Successfully authenticated with Gmail API using service account.")
    except Exception as e:
        logger.error(f"Failed to load service account credentials: {e}")
        return None

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}")
        return None

def search_emails(service, query):
    """Search for emails matching the query."""
    try:
        response = service.users().messages().list(userId='me', q=query).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
            if 'messages' in response:
                messages.extend(response['messages'])
        logger.info(f"Found {len(messages)} messages matching query: '{query}'")
        return messages
    except HttpError as error:
        logger.error(f'An error occurred searching emails with query "{query}": {error}')
        return []

def download_specific_attachments(service, message_id, download_to_dir, desired_filename_extension=".zip"):
    """Download specific attachments (e.g., only .zip files) from a message."""
    try:
        message = service.users().messages().get(userId='me', id=message_id).execute()
        parts = message['payload'].get('parts', [])
        downloaded_files_info = []

        if not os.path.exists(download_to_dir):
            os.makedirs(download_to_dir)
            logger.info(f"Created download directory: {download_to_dir}")

        for part in parts:
            filename = part.get('filename')
            if filename and (desired_filename_extension is None or filename.lower().endswith(desired_filename_extension.lower())):
                if 'data' in part['body']:
                    data = part['body']['data']
                else:
                    att_id = part['body']['attachmentId']
                    att = service.users().messages().attachments().get(userId='me', messageId=message_id, id=att_id).execute()
                    data = att['data']
                
                file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
                path = os.path.join(download_to_dir, filename)
                
                with open(path, 'wb') as f:
                    f.write(file_data)
                downloaded_files_info.append({'message_id': message_id, 'filename': filename, 'path': path})
                logger.info(f"Downloaded attachment: {filename} to {path} for message ID: {message_id}")
        
        return downloaded_files_info
    except HttpError as error:
        logger.error(f'An error occurred downloading attachments for message {message_id}: {error}')
        return []

def mark_email_as_read(service, message_id):
    """Marks an email as read by removing the UNREAD label."""
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        logger.info(f"Marked message {message_id} as read.")
        return True
    except HttpError as error:
        logger.error(f'An error occurred trying to mark message {message_id} as read: {error}')
        return False

def get_label_id(service, label_name):
    """Gets the ID of a label by its name. Creates the label if it doesn't exist."""
    try:
        labels_response = service.users().labels().list(userId='me').execute()
        labels = labels_response.get('labels', [])
        for label in labels:
            if label['name'] == label_name:
                return label['id']
        
        logger.info(f"Label '{label_name}' not found. Creating it.")
        new_label = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        created_label = service.users().labels().create(userId='me', body=new_label).execute()
        logger.info(f"Label '{label_name}' created with ID: {created_label['id']}")
        return created_label['id']
    except HttpError as error:
        logger.error(f'An error occurred while getting/creating label {label_name}: {error}')
        return None

def add_label_to_email(service, message_id, label_name):
    """Adds a label to the specified email message."""
    label_id = get_label_id(service, label_name)
    if not label_id:
        logger.error(f"Could not get or create label ID for '{label_name}'. Cannot add label to message {message_id}.")
        return False
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'addLabelIds': [label_id]}
        ).execute()
        logger.info(f"Added label '{label_name}' to message {message_id}.")
        return True
    except HttpError as error:
        logger.error(f"An error occurred trying to add label '{label_name}' to message {message_id}: {error}")
        return False

def remove_label_from_email(service, message_id, label_name):
    """Removes a label from the specified email message."""
    label_id = get_label_id(service, label_name) 
    if not label_id:
        logger.warning(f"Label '{label_name}' does not exist or couldn't be fetched. Cannot remove from message {message_id}.")
        return False 
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': [label_id]}
        ).execute()
        logger.info(f"Removed label '{label_name}' from message {message_id}.")
        return True
    except HttpError as error:
        logger.error(f"An error occurred trying to remove label '{label_name}' from message {message_id}: {error}")
        return False

def fetch_new_reports(service, search_query, download_to_dir, attachment_config):
    """
    Fetches new emails based on query, downloads specific attachments based on attachment_config,
    and returns list of dicts with message_id, path to downloaded file, original filename, and report_type.

    Args:
        service: Gmail API service object.
        search_query (str): The base Gmail search query.
        download_to_dir (str): Directory to download attachments to.
        attachment_config (dict): Configuration for attachments.
            Expected keys:
            'desired_filename_extension' (str): e.g., ".zip", ".csv", ".pdf"
            'report_type' (str): Identifier for the type of report, e.g., "KMERCHANT_ZIP", "EWALLET_CSV"
            'file_path_key' (str): Key to use in the result dict for the file path, e.g., "zip_path", "csv_path"
            'processed_label' (str): The label to check for exclusion in the query.
    """
    
    processed_label_name = attachment_config['processed_label']
    final_query = f"{search_query} -label:{processed_label_name}"
    
    messages = search_emails(service, final_query)
    all_downloaded_files = []
    if not messages:
        logger.info(f"No new messages found matching the query: {final_query} for report type: {attachment_config['report_type']}")
        return all_downloaded_files

    desired_extension = attachment_config['desired_filename_extension']
    report_type = attachment_config['report_type']
    file_path_key = attachment_config['file_path_key']

    for message_summary in messages:
        message_id = message_summary['id']
        logger.info(f"Processing message ID: {message_id} for report type: {report_type}")
        
        downloaded_attachments_info = download_specific_attachments(
            service, 
            message_id, 
            download_to_dir, 
            desired_filename_extension=desired_extension
        )
        
        for attachment_info in downloaded_attachments_info:
            # Ensure only one attachment of the desired type is processed per email,
            # or adjust if multiple attachments of the same type per email are expected.
            # For now, assumes the first one found is the target.
            if attachment_info['filename'].lower().endswith(desired_extension.lower()):
                all_downloaded_files.append({
                    'message_id': message_id,
                    file_path_key: attachment_info['path'],
                    'original_filename': attachment_info['filename'],
                    'report_type': report_type,
                    'processed_label': processed_label_name # Pass along for potential use in main
                })
                logger.info(f"Successfully prepared info for {attachment_info['filename']} (Message ID: {message_id}) as {report_type}")
                break # Process only the first matching attachment for this message. Remove if multiple are possible and needed.
            else:
                logger.warning(f"Skipping attachment {attachment_info['filename']} for message {message_id} as it does not match desired extension {desired_extension} (this should ideally not happen if download_specific_attachments works as expected).")

    logger.info(f"Fetched {len(all_downloaded_files)} reports of type '{report_type}'.")
    return all_downloaded_files

if __name__ == '__main__':
    # --- Configuration for standalone testing ---
    # Import configuration from config.py
    import sys
    # Add project root to sys.path to allow importing config if email_handler is in a subdirectory
    # This is mainly for when running `python src/email_handler.py` from the project root.
    PROJECT_ROOT_EH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if PROJECT_ROOT_EH not in sys.path:
        sys.path.append(PROJECT_ROOT_EH)
    
    try:
        from src import config # If running from project root: python -m src.email_handler
    except ImportError:
        import config # If running from src directory: python email_handler.py

    CREDENTIALS_FILE_PATH = config.GMAIL_CREDENTIALS_PATH
    TOKEN_FILE_PATH = config.GMAIL_TOKEN_PATH
    DOWNLOAD_DIR_PATH = config.DOWNLOAD_REPORTS_DIR
    
    # --- End Configuration ---

    print(f"Using credentials: {CREDENTIALS_FILE_PATH}")
    print(f"Using token file: {TOKEN_FILE_PATH}")
    print(f"Download directory: {DOWNLOAD_DIR_PATH}")

    if not os.path.exists(CREDENTIALS_FILE_PATH):
        logger.error(f"ERROR: Credentials file not found at {CREDENTIALS_FILE_PATH}")
        logger.error(f"Please ensure GMAIL_CREDENTIALS_PATH is set correctly in .env and points to a valid file.")
    else:
        gmail_service = get_gmail_service()
        
        if gmail_service:
            logger.info("Successfully authenticated with Gmail for __main__ test.")
            
            # Example usage for K-Merchant ZIP reports
            kmerchant_zip_config = {
                'desired_filename_extension': ".zip",
                'report_type': "KMERCHANT_ZIP",
                'file_path_key': "zip_path",
                'processed_label': LABEL_PROCESSED 
            }
            kmerchant_search_query = 'subject:("K-Merchant Reports as of") has:attachment'
            
            logger.info(f"Using search query for KMERCHANT_ZIP: {kmerchant_search_query} -label:{kmerchant_zip_config['processed_label']}")
            downloaded_zip_infos = fetch_new_reports(
                gmail_service, 
                kmerchant_search_query, 
                DOWNLOAD_DIR_PATH, 
                kmerchant_zip_config
            )
            
            if downloaded_zip_infos:
                logger.info(f"Successfully fetched and downloaded {len(downloaded_zip_infos)} K-Merchant ZIP report(s):")
                for report_info in downloaded_zip_infos:
                    logger.info(f"  Message ID: {report_info['message_id']}, ZIP Path: {report_info['zip_path']}, Type: {report_info['report_type']}")
            else:
                logger.info("No new K-Merchant ZIP reports were downloaded.")

            # Example usage for EWALLET_CSV reports
            ewallet_csv_config = {
                'desired_filename_extension': ".csv",
                'report_type': "EWALLET_CSV",
                'file_path_key': "csv_path",
                'processed_label': LABEL_EWALLET_CSV_PROCESSED
            }
            ewallet_csv_search_query = 'subject:("EWALLET REPORT") has:attachment filename:.csv'

            logger.info(f"Using search query for EWALLET_CSV: {ewallet_csv_search_query} -label:{ewallet_csv_config['processed_label']}")
            downloaded_csv_infos = fetch_new_reports(
                gmail_service,
                ewallet_csv_search_query,
                DOWNLOAD_DIR_PATH,
                ewallet_csv_config
            )

            if downloaded_csv_infos:
                logger.info(f"Successfully fetched and downloaded {len(downloaded_csv_infos)} eWallet CSV report(s):")
                for report_info in downloaded_csv_infos:
                    logger.info(f"  Message ID: {report_info['message_id']}, CSV Path: {report_info['csv_path']}, Type: {report_info['report_type']}")
            else:
                logger.info("No new eWallet CSV reports were downloaded.")

            # Example usage for EWALLET_ETAX_PDF reports
            ewallet_pdf_config = {
                'desired_filename_extension': ".pdf",
                'report_type': "EWALLET_ETAX_PDF",
                'file_path_key': "pdf_path",
                'processed_label': LABEL_EWALLET_ETAX_PDF_PROCESSED
            }
            ewallet_pdf_search_query = 'subject:("E-TAX INVOICE FOR EWALLET") has:attachment filename:.pdf'

            logger.info(f"Using search query for EWALLET_ETAX_PDF: {ewallet_pdf_search_query} -label:{ewallet_pdf_config['processed_label']}")
            downloaded_pdf_infos = fetch_new_reports(
                gmail_service,
                ewallet_pdf_search_query,
                DOWNLOAD_DIR_PATH,
                ewallet_pdf_config
            )

            if downloaded_pdf_infos:
                logger.info(f"Successfully fetched and downloaded {len(downloaded_pdf_infos)} eWallet E-Tax PDF report(s):")
                for report_info in downloaded_pdf_infos:
                    logger.info(f"  Message ID: {report_info['message_id']}, PDF Path: {report_info['pdf_path']}, Type: {report_info['report_type']}")
            else:
                logger.info("No new eWallet E-Tax PDF reports were downloaded.")
        else:
            logger.error("Failed to get Gmail service for __main__ test.")

    # TODO:
    # - Refine search query based on DESIGN_DOCUMENT.md
    # - Implement logic to mark emails as read or move them after processing.
    # - Integrate with main.py: email_handler fetches, returns path to downloaded ZIP.
    # - Handle potential errors more robustly.
    # - Ensure paths for CREDENTIALS_FILE, TOKEN_FILE, and DOWNLOAD_DIR are robust
    #   whether running standalone or as part of the larger application. 