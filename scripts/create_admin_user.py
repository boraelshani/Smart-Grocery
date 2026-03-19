#!/usr/bin/env python3
"""Create or update a website admin user."""

import os
import sys
from datetime import datetime, timezone

import bcrypt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from utils.db import get_db


ADMIN_EMAIL = "admin@smartgrocery.local"
ADMIN_PASSWORD = "Admin123!Smart"
ADMIN_NAME = "Website Admin"


def main():
    with app.app_context():
        db = get_db()
        if db is None:
            raise SystemExit("Database unavailable")

        now = datetime.now(timezone.utc)
        hashed_password = bcrypt.hashpw(
            ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        db.users.update_one(
            {"email": ADMIN_EMAIL},
            {
                "$set": {
                    "email": ADMIN_EMAIL,
                    "name": ADMIN_NAME,
                    "password": hashed_password,
                    "is_admin": True,
                    "shopping_list": [],
                    "total_cost": 0.0,
                    "seen_deals": [],
                    "updatedAt": now,
                },
                "$setOnInsert": {
                    "createdAt": now,
                },
            },
            upsert=True,
        )

        created = db.users.find_one(
            {"email": ADMIN_EMAIL},
            {"_id": 0, "email": 1, "name": 1, "is_admin": 1},
        )

    print("admin_user", created)
    print("plain_password", ADMIN_PASSWORD)


if __name__ == "__main__":
    main()
