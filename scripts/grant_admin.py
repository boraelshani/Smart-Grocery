#!/usr/bin/env python3
"""Grant admin privileges to a user by email in PostgreSQL."""

import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from models.postgres_models import db as sa_db, User


def main():
    if len(sys.argv) < 2:
        print("Usage: ./venv/bin/python scripts/grant_admin.py user@example.com")
        raise SystemExit(1)

    email = sys.argv[1].strip().lower()

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"No user found with email: {email}")
            raise SystemExit(2)

        user.is_admin = True
        user.updated_at = datetime.now(timezone.utc)
        sa_db.session.commit()

        print(f"Admin granted for: {email}")


if __name__ == "__main__":
    main()
