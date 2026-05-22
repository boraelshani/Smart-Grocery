"""
═══════════════════════════════════════════════════════════════════════════
DATABASE UTILITIES – PostgreSQL via SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
Provides centralized database access for the entire application.
═══════════════════════════════════════════════════════════════════════════
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Re-export the shared SQLAlchemy instance from postgres_models
from models.postgres_models import db

def init_db(app):
    """
    Initialize the SQLAlchemy connection for the Flask app.
    Call this once in app.py after creating the Flask instance.
    """
    database_url = os.environ.get('DATABASE_URL', '')

    if not database_url:
        print("[DB] WARNING: DATABASE_URL not set. Using SQLite fallback.")
        database_url = 'sqlite:///fallback.db'

    # SQLAlchemy config
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
        'pool_recycle': 1800,
    }

    db.init_app(app)

    with app.app_context():
        # Only create tables that don't exist yet — never alter existing Neon tables
        try:
            db.create_all()
        except Exception as e:
            print(f"[DB] Note: create_all skipped ({e})")

    print(f"[DB] PostgreSQL initialized: {database_url[:55]}...")


def get_db():
    """
    Return the SQLAlchemy session.
    """
    try:
        return db.session
    except Exception:
        return None
