-- SQL migration: create recommended indexes for performance
-- Run this file using psql or your preferred DB client. It is safe to run multiple times.

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

-- Additional single-column indexes (if not present)
CREATE INDEX IF NOT EXISTS ix_users_user_id ON users (user_id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at);
CREATE INDEX IF NOT EXISTS ix_notifications_user_email ON notifications (user_email);

-- End
