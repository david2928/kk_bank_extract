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
        print(f"Found {len(messages)} messages matching query: '{query}'")
        return messages
    except HttpError as error:
        print(f'An error occurred searching emails: {error}')
        return []

def download_specific_attachments(service, message_id, download_to_dir, desired_filename_extension=".zip"):
    """Download specific attachments (e.g., only .zip files) from a message."""
    try:
        message = service.users().messages().get(userId='me', id=message_id).execute()
        parts = message['payload'].get('parts', [])
        downloaded_files_info = []

        if not os.path.exists(download_to_dir):
            os.makedirs(download_to_dir)

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
                print(f"Downloaded attachment: {filename} to {path}")
        
        return downloaded_files_info
    except HttpError as error:
        print(f'An error occurred downloading attachments for message {message_id}: {error}')
        return []

def mark_email_as_read(service, message_id):
    """Marks an email as read by removing the UNREAD label."""
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Marked message {message_id} as read.")
        return True
    except HttpError as error:
        print(f'An error occurred trying to mark message {message_id} as read: {error}')
        return False

def get_label_id(service, label_name):
    """Gets the ID of a label by its name. Creates the label if it doesn't exist."""
    try:
        labels_response = service.users().labels().list(userId='me').execute()
        labels = labels_response.get('labels', [])
        for label in labels:
            if label['name'] == label_name:
                return label['id']
        
        # Label not found, create it
        print(f"Label '{label_name}' not found. Creating it.")
        new_label = {
            'name': label_name,
            'labelListVisibility': 'labelShow',  # Show in label list
            'messageListVisibility': 'show' # Show in message list (corrected from 'messageShow')
        }
        created_label = service.users().labels().create(userId='me', body=new_label).execute()
        print(f"Label '{label_name}' created with ID: {created_label['id']}")
        return created_label['id']
    except HttpError as error:
        print(f'An error occurred while getting/creating label {label_name}: {error}')
        return None

def add_label_to_email(service, message_id, label_name):
    """Adds a label to the specified email message."""
    label_id = get_label_id(service, label_name)
    if not label_id:
        return False
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'addLabelIds': [label_id]}
        ).execute()
        print(f"Added label '{label_name}' to message {message_id}.")
        return True
    except HttpError as error:
        print(f"An error occurred trying to add label '{label_name}' to message {message_id}: {error}")
        return False

def remove_label_from_email(service, message_id, label_name):
    """Removes a label from the specified email message."""
    label_id = get_label_id(service, label_name) # We need the ID to remove it
    if not label_id:
        # If the label doesn't exist at all, we can't remove it from a message.
        print(f"Label '{label_name}' does not exist. Cannot remove from message {message_id}.")
        return False 
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': [label_id]}
        ).execute()
        print(f"Removed label '{label_name}' from message {message_id}.")
        return True
    except HttpError as error:
        # It's possible the message didn't have the label, which can sometimes cause an error or just do nothing.
        # Depending on API behavior, this error might indicate the label wasn't on the message.
        print(f"An error occurred trying to remove label '{label_name}' from message {message_id}: {error}")
        return False

def fetch_new_reports(service, search_query, download_to_dir):
    """
    Fetches new emails based on query, downloads .zip attachments, 
    and returns list of dicts with message_id and path to downloaded zip.
    """
    messages = search_emails(service, search_query)
    all_downloaded_zips = []
    if not messages:
        print("No new messages found matching the query.")
        return all_downloaded_zips

    for message_summary in messages:
        message_id = message_summary['id']
        print(f"Processing message ID: {message_id}")
        
        # Fetch full message details to check headers like Subject more easily if needed
        # msg_detail = service.users().messages().get(userId='me', id=message_id).execute()
        # subject_header = next((h['value'] for h in msg_detail['payload']['headers'] if h['name'] == 'Subject'), None)
        # print(f"  Subject: {subject_header}")

        downloaded_attachments_info = download_specific_attachments(service, message_id, download_to_dir, desired_filename_extension=".zip")
        
        for attachment_info in downloaded_attachments_info:
            all_downloaded_zips.append({
                'message_id': message_id, # Keep message_id for marking as read later
                'zip_path': attachment_info['path'],
                'original_filename': attachment_info['filename']
            })
            
    return all_downloaded_zips

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
        print(f"ERROR: Credentials file not found at {CREDENTIALS_FILE_PATH}")
        print(f"Please ensure GMAIL_CREDENTIALS_PATH is set correctly in .env and points to a valid file.")
    else:
        gmail_service = get_gmail_service()
        
        if gmail_service:
            print("Successfully authenticated with Gmail.")
            
            # Updated test search query
            test_search_query = f'subject:("K-Merchant Reports as of") has:attachment -label:{LABEL_PROCESSED}'
            print(f"Using search query: {test_search_query}")

            downloaded_report_infos = fetch_new_reports(gmail_service, test_search_query, DOWNLOAD_DIR_PATH)
            
            if downloaded_report_infos:
                print(f"Successfully fetched and downloaded {len(downloaded_report_infos)} report(s):")
                for report_info in downloaded_report_infos:
                    print(f"  Message ID: {report_info['message_id']}, ZIP Path: {report_info['zip_path']}")
                    # Example of marking as read (you'd do this after successful processing in main.py)
                    # mark_email_as_read(gmail_service, report_info['message_id'])
            else:
                print("No new reports were downloaded.")
        else:
            print("Failed to get Gmail service.")

    # TODO:
    # - Refine search query based on DESIGN_DOCUMENT.md
    # - Implement logic to mark emails as read or move them after processing.
    # - Integrate with main.py: email_handler fetches, returns path to downloaded ZIP.
    # - Handle potential errors more robustly.
    # - Ensure paths for CREDENTIALS_FILE, TOKEN_FILE, and DOWNLOAD_DIR are robust
    #   whether running standalone or as part of the larger application. 