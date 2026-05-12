#!/usr/bin/env python3
"""
Run database migrations
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app import app
from models.postgres_models import db
from sqlalchemy import text

def run_migration(migration_file):
    """Run a SQL migration file"""
    migration_path = Path(__file__).parent.parent / 'migrations' / migration_file
    
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False
    
    print(f"📄 Reading migration: {migration_file}")
    with open(migration_path, 'r') as f:
        sql = f.read()
    
    try:
        print(f"🔄 Running migration...")
        with app.app_context():
            with db.engine.begin() as conn:
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
                for stmt in statements:
                    if stmt:
                        print(f"  Executing: {stmt[:80]}...")
                        conn.execute(text(stmt))
        
        print(f"✅ Migration completed successfully!")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/run_migration.py <migration_file.sql>")
        print("\nAvailable migrations:")
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        if migrations_dir.exists():
            for f in sorted(migrations_dir.glob('*.sql')):
                print(f"  - {f.name}")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    success = run_migration(migration_file)
    sys.exit(0 if success else 1)
