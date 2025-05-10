import os
from dotenv import load_dotenv

# Determine the absolute path to the project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file in the project root
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ZIP File Configuration
ZIP_PASSWORD = os.getenv("ZIP_PASSWORD")

# Gmail Configuration
GMAIL_USER_EMAIL = os.getenv("GMAIL_USER_EMAIL")
GMAIL_CREDENTIALS_PATH_REL = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
GMAIL_TOKEN_PATH_REL = os.getenv("GMAIL_TOKEN_PATH", "token.json")
DOWNLOAD_REPORTS_DIR_REL = os.getenv("DOWNLOAD_REPORTS_DIR", "downloaded_reports/")

# Convert to absolute paths, assuming relative paths are from project root
GMAIL_CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, GMAIL_CREDENTIALS_PATH_REL)
GMAIL_TOKEN_PATH = os.path.join(PROJECT_ROOT, GMAIL_TOKEN_PATH_REL)
DOWNLOAD_REPORTS_DIR = os.path.join(PROJECT_ROOT, DOWNLOAD_REPORTS_DIR_REL)

# Ensure the download directory exists
if not os.path.exists(DOWNLOAD_REPORTS_DIR):
    os.makedirs(DOWNLOAD_REPORTS_DIR)

# Google Drive Configuration
GDRIVE_ROOT_FOLDER_ID = os.getenv("GDRIVE_ROOT_FOLDER_ID", "1FQVq8tF-Wm4PHTzo8Ah5TRU7b69dsM7B") # Updated to the new folder ID

# Google Service Account Configuration
GOOGLE_SERVICE_ACCOUNT_KEY_PATH_REL = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "service_account.json") # Relative to project root by default
GOOGLE_SERVICE_ACCOUNT_KEY_PATH = os.path.join(PROJECT_ROOT, GOOGLE_SERVICE_ACCOUNT_KEY_PATH_REL)

# Admin email for notifications
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# You can add helper functions here if needed, for example, to check if critical variables are set:
def get_required_env(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Error: Environment variable {var_name} is not set.")
    return value

# Example of using the helper for critical vars (optional, depends on how strict you want to be at startup)
# SUPABASE_URL = get_required_env("SUPABASE_URL")
# SUPABASE_KEY = get_required_env("SUPABASE_KEY")
# Placeholder for configuration loading 

if __name__ == '__main__':
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"Supabase Key: {SUPABASE_KEY is not None}") # Print True if key is loaded
    print(f"Zip Password: {ZIP_PASSWORD is not None}") # Print True if password is loaded
    print(f"Gmail Credentials Path: {GMAIL_CREDENTIALS_PATH}")
    print(f"Gmail Token Path: {GMAIL_TOKEN_PATH}")
    print(f"Download Reports Dir: {DOWNLOAD_REPORTS_DIR}")
    print(f"Download directory exists: {os.path.exists(DOWNLOAD_REPORTS_DIR)}")
    print(f"Google Drive Root Folder ID: {GDRIVE_ROOT_FOLDER_ID}")
    print(f"Google Service Account Key Path: {GOOGLE_SERVICE_ACCOUNT_KEY_PATH}")