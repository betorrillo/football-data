#!/usr/bin/env python3
"""
Upload key analysis files to Google Drive folder.
Used by GitHub Actions after data update to sync files for Claude AI.

Requires:
  - GDRIVE_SERVICE_ACCOUNT_JSON env var (JSON key content)
  - GDRIVE_FOLDER_ID env var (Drive folder ID)
  - pip install google-api-python-client google-auth

Usage:
  python3 scripts/upload_to_drive.py
"""

import glob
import json
import os
import sys
from datetime import datetime

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("ERROR: google-api-python-client and google-auth not installed")
    print("Run: pip install google-api-python-client google-auth")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now().strftime("%Y-%m-%d")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """Create authenticated Google Drive service from env var."""
    sa_json = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        print("ERROR: GDRIVE_SERVICE_ACCOUNT_JSON env var not set")
        sys.exit(1)

    try:
        sa_info = json.loads(sa_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: GDRIVE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}")
        print(f"  First 50 chars: {sa_json[:50]}...")
        print(f"  Length: {len(sa_json)} chars")
        print("  Make sure you pasted the ENTIRE JSON file content as the secret value")
        sys.exit(1)

    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def find_file_in_folder(service, folder_id, filename):
    """Find a file by name in a specific folder. Returns file ID or None."""
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query, fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def upload_or_update(service, folder_id, local_path, drive_filename=None):
    """Upload a file to Drive, or update it if it already exists."""
    if not os.path.exists(local_path):
        print(f"  SKIP (not found): {local_path}")
        return None

    filename = drive_filename or os.path.basename(local_path)
    file_size = os.path.getsize(local_path)

    media = MediaFileUpload(local_path, mimetype="application/json", resumable=False)

    # Check if file already exists in folder
    existing_id = find_file_in_folder(service, folder_id, filename)

    if existing_id:
        # Update existing file (uses owner's quota, not SA's)
        file = service.files().update(
            fileId=existing_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
        action = "UPDATED"
    else:
        # SA can't create files on personal Gmail (no storage quota).
        # User must pre-create these files manually in the Drive folder.
        print(f"  SKIP (not in Drive yet — create '{filename}' manually): {local_path}")
        return None

    file_id = file.get("id")
    print(f"  {action}: {filename} ({file_size:,} bytes) -> Drive ID: {file_id}")
    return file_id


def main():
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("ERROR: GDRIVE_FOLDER_ID env var not set")
        sys.exit(1)

    print(f"Google Drive Upload — {TODAY}")
    print("=" * 50)

    service = get_drive_service()
    uploaded = 0

    # Files to sync — all use FIXED names so they get updated (not created) in Drive.
    # User must pre-create these files once in the Drive folder.
    FILES_TO_SYNC = [
        # (local_path_or_glob, fixed_drive_name)
        (os.path.join(BASE_DIR, "status.json"), "status.json"),
        (os.path.join(BASE_DIR, "agent_bundle.json"), "agent_bundle.json"),
    ]

    # Find latest dated files and upload with fixed names
    analysis = sorted(glob.glob(os.path.join(BASE_DIR, "analysis_pack_*.json")), reverse=True)
    if analysis:
        FILES_TO_SYNC.append((analysis[0], "analysis_pack.json"))

    refs = sorted(glob.glob(os.path.join(BASE_DIR, "referees", "all_referees_*.json")), reverse=True)
    if refs:
        FILES_TO_SYNC.append((refs[0], "all_referees.json"))

    for path, drive_name in FILES_TO_SYNC:
        if upload_or_update(service, folder_id, path, drive_filename=drive_name):
            uploaded += 1

    print(f"\n{'='*50}")
    print(f"UPLOAD COMPLETE — {uploaded} files synced to Drive")

    if uploaded == 0:
        print("WARNING: No files were uploaded! Create these files manually in your Drive folder:")
        for _, name in FILES_TO_SYNC:
            print(f"  - {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
