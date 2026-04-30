#!/usr/bin/env python3
"""Create a full logical backup of every MongoDB collection.

The backup is written as gzipped JSONL files so ObjectIds and datetimes remain
round-trippable with bson.json_util.
"""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import certifi
from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def _get_mongo_uri() -> str:
    return os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/smart_grocery"


def _get_database_name(uri: str) -> str:
    explicit = os.environ.get("DATABASE_NAME")
    if explicit:
        return explicit
    parsed = urlparse(uri)
    return (parsed.path or "").lstrip("/") or "smart_grocery"


def _connect(uri: str) -> MongoClient:
    try:
        return MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    except Exception:
        return MongoClient(uri, serverSelectionTimeoutMS=8000)


def create_backup(output_root: str | None = None) -> dict:
    uri = _get_mongo_uri()
    db_name = _get_database_name(uri)
    client = _connect(uri)
    client.admin.command("ping")

    db = client[db_name]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"backup_{timestamp}"
    backup_root = Path(output_root or os.environ.get("MONGODB_BACKUP_DIR", "backups/mongodb"))
    backup_dir = backup_root / f"{db_name}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "database": db_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "collections": [],
    }

    for collection_name in sorted(db.list_collection_names()):
        collection = db[collection_name]
        docs_path = backup_dir / f"{collection_name}.jsonl.gz"
        count = 0

        with gzip.open(docs_path, "wt", encoding="utf-8") as handle:
            for doc in collection.find({}):
                handle.write(json_util.dumps(doc))
                handle.write("\n")
                count += 1

        manifest["collections"].append(
            {
                "name": collection_name,
                "count": count,
                "indexes": collection.index_information(),
                "file": docs_path.name,
            }
        )

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    try:
        db.backup_runs.update_one(
            {"backupId": backup_id},
            {
                "$set": {
                    "backupId": backup_id,
                    "database": db_name,
                    "backupDir": str(backup_dir),
                    "createdAt": datetime.now(timezone.utc),
                    "status": "completed",
                    "collections": [
                        {"name": row["name"], "count": row["count"]}
                        for row in manifest["collections"]
                    ],
                }
            },
            upsert=True,
        )
    except Exception:
        pass

    return {"database": db_name, "backup_dir": str(backup_dir), "collections": manifest["collections"]}


def main() -> None:
    result = create_backup()
    print("MongoDB backup completed")
    print(f"Database: {result['database']}")
    print(f"Backup directory: {result['backup_dir']}")
    for collection in result["collections"]:
        print(f"  {collection['name']}: {collection['count']} documents")


if __name__ == "__main__":
    main()