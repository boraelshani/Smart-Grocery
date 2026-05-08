#!/usr/bin/env python3
"""Create or update a website admin user in PostgreSQL."""

import os
import sys
from datetime import datetime, timezone

import bcrypt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from models.postgres_models import db as sa_db, User

ADMIN_EMAIL = "admin@smartgrocery.local"
ADMIN_PASSWORD = "Admin123!Smart"
ADMIN_NAME = "Website Admin"


def main():
    with app.app_context():
        hashed_password = bcrypt.hashpw(
            ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        user = User.query.filter_by(email=ADMIN_EMAIL).first()
        if user:
            user.password_hash = hashed_password
            user.is_admin = True
            user.name = ADMIN_NAME
            user.updated_at = datetime.now(timezone.utc)
            print(f"Updated existing admin user: {ADMIN_EMAIL}")
        else:
            user = User(
                user_id=f"admin_{int(datetime.now(timezone.utc).timestamp())}",
                email=ADMIN_EMAIL,
                password_hash=hashed_password,
                name=ADMIN_NAME,
                is_admin=True,
                language="en",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            sa_db.session.add(user)
            print(f"Created new admin user: {ADMIN_EMAIL}")

        sa_db.session.commit()

        created = User.query.filter_by(email=ADMIN_EMAIL).first()
        print("admin_user", {
            "email": created.email,
            "name": created.name,
            "is_admin": created.is_admin,
        })
        print("plain_password", ADMIN_PASSWORD)


if __name__ == "__main__":
    main()
