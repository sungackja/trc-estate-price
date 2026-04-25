import argparse
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests

from config import DATA_DIR, DB_PATH, REQUEST_TIMEOUT_SECONDS


REPO_FULL_NAME = "sungackja/trc-estate-price"
ARTIFACT_NAME = "trades-sqlite-snapshot"
API_BASE_URL = f"https://api.github.com/repos/{REPO_FULL_NAME}"


def github_headers():
    headers = {"User-Agent": "trc-estate-price-db-sync"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_json(url):
    response = requests.get(url, headers=github_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def find_latest_snapshot_artifact():
    data = request_json(f"{API_BASE_URL}/actions/artifacts?per_page=100")
    artifacts = [
        artifact
        for artifact in data.get("artifacts", [])
        if artifact.get("name") == ARTIFACT_NAME and not artifact.get("expired")
    ]
    if not artifacts:
        return None

    return sorted(artifacts, key=lambda artifact: artifact.get("created_at", ""), reverse=True)[0]


def download_artifact(artifact):
    url = artifact["archive_download_url"]
    response = requests.get(url, headers=github_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content


def extract_sqlite_bytes(artifact_zip_bytes):
    with zipfile.ZipFile(BytesIO(artifact_zip_bytes)) as artifact_zip:
        inner_names = artifact_zip.namelist()
        if "trades-sqlite-snapshot.zip" not in inner_names:
            raise RuntimeError(f"Artifact did not contain trades-sqlite-snapshot.zip: {inner_names}")

        inner_zip_bytes = artifact_zip.read("trades-sqlite-snapshot.zip")

    with zipfile.ZipFile(BytesIO(inner_zip_bytes)) as db_zip:
        db_names = db_zip.namelist()
        sqlite_name = next((name for name in db_names if name.endswith("trades.sqlite3")), None)
        if sqlite_name is None:
            raise RuntimeError(f"Snapshot did not contain trades.sqlite3: {db_names}")

        return db_zip.read(sqlite_name)


def backup_existing_db():
    if not DB_PATH.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = DATA_DIR / f"trades.local-backup-{timestamp}.sqlite3"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def sync_database():
    artifact = find_latest_snapshot_artifact()
    if artifact is None:
        raise RuntimeError(
            "No trades-sqlite-snapshot artifact found yet. Run the Daily record-high report workflow once first."
        )

    print(f"Found artifact #{artifact['id']} created at {artifact['created_at']}")
    sqlite_bytes = extract_sqlite_bytes(download_artifact(artifact))

    DATA_DIR.mkdir(exist_ok=True)
    backup_path = backup_existing_db()

    with tempfile.NamedTemporaryFile(delete=False, dir=DATA_DIR, suffix=".sqlite3") as temp_file:
        temp_file.write(sqlite_bytes)
        temp_path = Path(temp_file.name)

    temp_path.replace(DB_PATH)
    print(f"Updated local DB: {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    if backup_path:
        print(f"Backup: {backup_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Download the latest GitHub Actions SQLite DB snapshot.")
    return parser.parse_args()


if __name__ == "__main__":
    parse_args()
    sync_database()
