from app import app
from models.postgres_models import db
from sqlalchemy import text
import sys

def backup():
    with app.app_context():
        print("Creating backups 'products_backup' & 'offers_backup'...")
        db.session.execute(text("DROP TABLE IF EXISTS products_backup;"))
        db.session.execute(text("DROP TABLE IF EXISTS offers_backup;"))
        db.session.execute(text("CREATE TABLE products_backup AS SELECT * FROM products;"))
        db.session.execute(text("CREATE TABLE offers_backup AS SELECT * FROM offers;"))
        db.session.commit()
        print("✅ Backups created successfully!")

def rollback():
    with app.app_context():
        print("Rolling back tables from backups...")
        # Since products has a foreign key to categories and offers to products, 
        # dropping could be messy, so we TRUNCATE and INSERT.
        # But wait, truncate offers AND products:
        db.session.execute(text("TRUNCATE offers, products CASCADE;"))
        db.session.execute(text("INSERT INTO products SELECT * FROM products_backup;"))
        db.session.execute(text("INSERT INTO offers SELECT * FROM offers_backup;"))
        db.session.commit()
        print("✅ Rollback successful! Data restored from backup.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        rollback()
    else:
        backup()