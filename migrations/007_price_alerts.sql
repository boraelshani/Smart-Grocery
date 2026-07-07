CREATE TABLE IF NOT EXISTS price_alerts (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    target_price NUMERIC(10, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    triggered_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_price_alerts_user ON price_alerts(user_email);
CREATE INDEX IF NOT EXISTS ix_price_alerts_product ON price_alerts(product_id);
CREATE INDEX IF NOT EXISTS ix_price_alerts_active ON price_alerts(is_active);
