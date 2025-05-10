import os.path
import logging
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from . import config

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Assuming your existing email_handler.py has the get_gmail_service structure
# which handles token.json, credentials.json, and SCOPES.
# We will leverage that existing authentication flow by passing the creds or by rebuilding service with Drive scopes.
# For simplicity here, let's assume the get_gmail_service in email_handler already includes Drive scopes
# or we can call it directly from there. The SCOPES are global to that authentication.

from src import config # To get GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from src.email_handler import get_gmail_service # We can reuse this if scopes are updated there

logger = logging.getLogger(__name__)

def get_gdrive_service():
    """Authenticates with Google Drive API using a service account and returns the service object."""
    creds = None
    service_account_key_path = config.GOOGLE_SERVICE_ACCOUNT_KEY_PATH

    if not os.path.exists(service_account_key_path):
        logger.error(f"Service account key file not found at {service_account_key_path}. "
                     f"Ensure it's correctly placed and GOOGLE_SERVICE_ACCOUNT_KEY_PATH is set.")
        return None

    try:
        creds = Credentials.from_service_account_file(
            service_account_key_path,
            scopes=SCOPES
        )
        logger.info("Successfully authenticated with Google Drive API using service account.")
    except Exception as e:
        logger.error(f"Failed to load service account credentials for Drive: {e}")
        return None

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to build Google Drive service: {e}")
        return None

def find_or_create_folder(service, parent_folder_id, folder_name):
    """
    Finds a folder by name within a parent folder. If not found, creates it.
    Returns the folder ID or None if an error occurs.
    """
    try:
        query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        folders = response.get('files', [])
        if folders:
            logger.info(f"Found folder '{folder_name}' with ID: {folders[0].get('id')}")
            return folders[0].get('id')
        else:
            logger.info(f"Folder '{folder_name}' not found in parent ID '{parent_folder_id}'. Creating it.")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            logger.info(f"Created folder '{folder_name}' with ID: {folder.get('id')}")
            return folder.get('id')
    except HttpError as error:
        logger.error(f"An error occurred trying to find/create folder '{folder_name}': {error}")
        return None

def upload_file_to_gdrive(service, local_file_path, gdrive_folder_id, remote_filename=None):
    """
    Uploads a local file to the specified Google Drive folder.
    Returns the file ID if successful, None otherwise.
    """
    if not os.path.exists(local_file_path):
        logger.error(f"Local file not found for upload: {local_file_path}")
        return None

    file_basename = os.path.basename(local_file_path)
    upload_filename = remote_filename if remote_filename else file_basename

    try:
        file_metadata = {
            'name': upload_filename,
            'parents': [gdrive_folder_id]
        }
        media = MediaFileUpload(local_file_path, resumable=True)
        request = service.files().create(body=file_metadata, media_body=media, fields='id')
        
        response = None
        file_id = None
        logger.info(f"Starting upload of {local_file_path} as '{upload_filename}' to Drive folder ID {gdrive_folder_id}.")
        # resumable upload loop
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Uploaded {int(status.progress() * 100)}% of {upload_filename}")
        
        if response and response.get('id'):
            file_id = response.get('id')
            logger.info(f"Successfully uploaded '{upload_filename}' (ID: {file_id}) to Google Drive folder ID {gdrive_folder_id}.")
            return file_id
        else:
            logger.error(f"Google Drive upload of '{upload_filename}' failed. No file ID in response. Response: {response}")
            return None
            
    except HttpError as error:
        logger.error(f"An HttpError occurred during Google Drive upload of '{upload_filename}': {error}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Google Drive upload of '{upload_filename}': {e}", exc_info=True)
        return None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("Testing Google Drive Handler...")

    # Ensure your .env file is loaded and config is accessible if you run this directly
    # You might need to adjust pathing for config if running from a different CWD
    # from dotenv import load_dotenv
    # load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env')) # Adjust path as needed
    # import config # Re-import or ensure it's loaded with new values

    if not config.GOOGLE_SERVICE_ACCOUNT_KEY_PATH or not os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_KEY_PATH):
        logger.error("Service account key path not configured or file not found. Set GOOGLE_SERVICE_ACCOUNT_KEY_PATH in .env")
    elif not config.GDRIVE_ROOT_FOLDER_ID:
        logger.error("GDRIVE_ROOT_FOLDER_ID not set in .env")
    else:
        drive_service = get_gdrive_service()
        if drive_service:
            logger.info("Google Drive service obtained successfully.")
            
            # Test find_or_create_folder
            year_folder_name = "2024"
            month_folder_name = "202407"
            day_folder_name = "2024-07-30"
            
            root_folder_id = config.GDRIVE_ROOT_FOLDER_ID
            
            year_folder_id = find_or_create_folder(drive_service, year_folder_name, root_folder_id)
            if year_folder_id:
                logger.info(f"Year folder '{year_folder_name}' ID: {year_folder_id}")
                month_folder_id = find_or_create_folder(drive_service, month_folder_name, year_folder_id)
                if month_folder_id:
                    logger.info(f"Month folder '{month_folder_name}' ID: {month_folder_id}")
                    day_folder_id = find_or_create_folder(drive_service, day_folder_name, month_folder_id)
                    if day_folder_id:
                        logger.info(f"Day folder '{day_folder_name}' ID: {day_folder_id}")
                        
                        # Test upload_file_to_gdrive
                        # Create a dummy file to upload
                        dummy_file_name = "test_upload.txt"
                        with open(dummy_file_name, "w") as f:
                            f.write("This is a test file for Google Drive upload.")
                        
                        file_metadata = upload_file_to_gdrive(drive_service, dummy_file_name, day_folder_id)
                        if file_metadata:
                            logger.info(f"File '{dummy_file_name}' uploaded successfully. ID: {file_metadata.get('id')}")
                        else:
                            logger.error(f"Failed to upload '{dummy_file_name}'.")
                        
                        # Clean up dummy file
                        os.remove(dummy_file_name)
                    else:
                        logger.error(f"Could not find or create day folder '{day_folder_name}'.")
                else:
                    logger.error(f"Could not find or create month folder '{month_folder_name}'.")
            else:
                logger.error(f"Could not find or create year folder '{year_folder_name}'.")
        else:
            logger.error("Failed to obtain Google Drive service.") 