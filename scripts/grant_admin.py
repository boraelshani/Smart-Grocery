#!/usr/bin/env python3
"""Grant admin privileges to a user by email in MongoDB users collection."""

import os
import sys

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient


def main():
    if len(sys.argv) < 2:
        print("Usage: ./venv/bin/python scripts/grant_admin.py user@example.com")
        raise SystemExit(1)

    email = sys.argv[1].strip().lower()
    load_dotenv()

    uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/smart_grocery"
    db_name = os.environ.get("DATABASE_NAME") or "smart_grocery"

    client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    db = client[db_name]

    result = db.users.update_one({"email": email}, {"$set": {"is_admin": True}}, upsert=False)
    if result.matched_count == 0:
        print(f"No user found with email: {email}")
        raise SystemExit(2)

    print(f"Admin granted for: {email}")


if __name__ == "__main__":
    main()
