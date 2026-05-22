"""Add recommended indexes

Revision ID: 0001_add_indexes
Revises: 
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_add_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_categories_parent_id ON categories (parent_id);
    CREATE INDEX IF NOT EXISTS ix_categories_slug ON categories (slug);

    CREATE INDEX IF NOT EXISTS ix_products_category_id ON products (category_id);
    CREATE INDEX IF NOT EXISTS ix_products_brand ON products (brand);
    CREATE INDEX IF NOT EXISTS ix_products_created_at ON products (created_at);

    CREATE INDEX IF NOT EXISTS ix_product_store_store_available ON product_store (store_id, is_available);
    CREATE INDEX IF NOT EXISTS ix_product_store_product_available_seen ON product_store (product_id, is_available, last_seen);

    CREATE INDEX IF NOT EXISTS ix_price_history_product_changed ON price_history (product_id, changed_at);
    CREATE INDEX IF NOT EXISTS ix_price_history_store_changed ON price_history (store_id, changed_at);

    CREATE INDEX IF NOT EXISTS ix_pending_products_status_created ON pending_products (status, created_at);
    CREATE INDEX IF NOT EXISTS ix_pending_products_submitted_by ON pending_products (submitted_by);

    CREATE INDEX IF NOT EXISTS ix_users_user_id ON users (user_id);
    CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
    CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at);
    CREATE INDEX IF NOT EXISTS ix_notifications_user_email ON notifications (user_email);
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS ix_categories_parent_id;
    DROP INDEX IF EXISTS ix_categories_slug;

    DROP INDEX IF EXISTS ix_products_category_id;
    DROP INDEX IF EXISTS ix_products_brand;
    DROP INDEX IF EXISTS ix_products_created_at;

    DROP INDEX IF EXISTS ix_product_store_store_available;
    DROP INDEX IF EXISTS ix_product_store_product_available_seen;

    DROP INDEX IF EXISTS ix_price_history_product_changed;
    DROP INDEX IF EXISTS ix_price_history_store_changed;

    DROP INDEX IF EXISTS ix_pending_products_status_created;
    DROP INDEX IF EXISTS ix_pending_products_submitted_by;

    DROP INDEX IF EXISTS ix_users_user_id;
    DROP INDEX IF EXISTS ix_users_email;
    DROP INDEX IF EXISTS ix_notifications_created_at;
    DROP INDEX IF EXISTS ix_notifications_user_email;
    """)
