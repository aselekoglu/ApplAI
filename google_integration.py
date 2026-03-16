import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

# Full Drive scope so we can create, update and share files
SCOPES = ['https://www.googleapis.com/auth/drive']
OAUTH_CREDENTIALS_FILE = 'google_oauth_credentials.json'
TOKEN_FILE = 'google_token.json'


def get_drive_service():
    """
    Authenticate via OAuth (user account). On the first run, opens a browser
    for a one-time login and caches the token to google_token.json.
    Subsequent calls reuse the cached token silently.
    """
    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        print("google_credentials.json not found.")
        return None

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh or do initial OAuth flow if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Failed to build Drive service: {e}")
        return None


def upload_to_drive(file_path: str, mime_type: str, convert_to_docs: bool = False):
    """
    Uploads a file to the user's Google Drive folder specified by GOOGLE_DRIVE_FOLDER_ID in .env.
    If convert_to_docs=True, converts .docx to a native editable Google Doc.
    Deduplicates: removes any existing file with the same name before uploading.
    Returns the webViewLink of the uploaded file.
    """
    service = get_drive_service()
    if not service:
        return None

    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        print("GOOGLE_DRIVE_FOLDER_ID not set in .env")
        return None

    file_name = os.path.basename(file_path)

    # Remove duplicate files with the same name in the target folder
    try:
        existing = service.files().list(
            q=f"name='{file_name}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        for f in existing.get("files", []):
            service.files().delete(fileId=f["id"]).execute()
    except Exception as e:
        print(f"Warning: could not clean up existing files: {e}")

    file_metadata = {'name': file_name, 'parents': [folder_id]}

    # Convert to native Google Doc format if requested
    if convert_to_docs and file_path.endswith('.docx'):
        file_metadata['mimeType'] = 'application/vnd.google-apps.document'

    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

    try:
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        return uploaded_file.get('webViewLink')
    except Exception as e:
        print(f"Error uploading to Drive: {e}")
        return None


if __name__ == "__main__":
    service = get_drive_service()
    if service:
        print("Successfully authenticated with Google Drive!")
        test_path = "docs/Tailored_CV.docx"
        if os.path.exists(test_path):
            url = upload_to_drive(test_path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", convert_to_docs=True)
            if url:
                print(f"Upload successful! View at: {url}")
            else:
                print("Upload returned None.")
    else:
        print("Failed to authenticate.")




