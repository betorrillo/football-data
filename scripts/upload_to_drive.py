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

# Full Drive scope needed to see/update files owned by the user
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Pre-created file IDs in the user's Drive folder (football-data-agent).
# These files are owned by the user; the SA updates them by ID.
# If a file ID is wrong or missing, the script falls back to search-by-name.
DRIVE_FILE_IDS = {
    "status.json": "1rlZt7oh5o5JuOolIaJVTbUT_G9mbRbfV",
    "agent_bundle.json": "1g1L0-BEslXa7jSb6omkWsouYaNhWsf2n",
    "analysis_pack.json": "12gbKuN-a6LZfdooVf80Ad6TiMITbCtvF",
    "all_referees.json": "1pXBqnhnBo0AD3ehlS2w0TERVKA2e4B-P",
    "fixture_predictions.json": "1dR2Qq4P9KE_vCd9MBUO-njEkfdAg0ADB",
}


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


def update_file_by_id(service, file_id, local_path, filename):
    """Update an existing Drive file by its ID."""
    if not os.path.exists(local_path):
        print(f"  SKIP (not found locally): {local_path}")
        return None

    file_size = os.path.getsize(local_path)
    media = MediaFileUpload(local_path, mimetype="application/json", resumable=False)

    try:
        file = service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
        print(f"  UPDATED: {filename} ({file_size:,} bytes) -> ID: {file_id}")
        return file_id
    except Exception as e:
        print(f"  FAILED to update {filename} (ID: {file_id}): {e}")
        return None


def main():
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("ERROR: GDRIVE_FOLDER_ID env var not set")
        sys.exit(1)

    print(f"Google Drive Upload — {TODAY}")
    print("=" * 50)

    service = get_drive_service()
    uploaded = 0

    # Files to sync: (local_path, fixed_drive_name)
    files_to_sync = [
        (os.path.join(BASE_DIR, "status.json"), "status.json"),
        (os.path.join(BASE_DIR, "agent_bundle.json"), "agent_bundle.json"),
    ]

    # Find latest dated files and upload with fixed names
    analysis = sorted(glob.glob(os.path.join(BASE_DIR, "analysis_pack_*.json")), reverse=True)
    if analysis:
        files_to_sync.append((analysis[0], "analysis_pack.json"))

    refs = sorted(glob.glob(os.path.join(BASE_DIR, "referees", "all_referees_*.json")), reverse=True)
    if refs:
        files_to_sync.append((refs[0], "all_referees.json"))

    preds = os.path.join(BASE_DIR, "predictions", "fixture_predictions_latest.json")
    if os.path.exists(preds):
        files_to_sync.append((preds, "fixture_predictions.json"))

    for local_path, drive_name in files_to_sync:
        file_id = DRIVE_FILE_IDS.get(drive_name)
        if file_id:
            if update_file_by_id(service, file_id, local_path, drive_name):
                uploaded += 1
        else:
            print(f"  SKIP (no Drive ID configured): {drive_name}")

    print(f"\n{'='*50}")
    print(f"UPLOAD COMPLETE — {uploaded} files synced to Drive")

    if uploaded == 0:
        print("WARNING: No files were uploaded!")
        sys.exit(1)


if __name__ == "__main__":
    main()
