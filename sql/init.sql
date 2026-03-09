CREATE TABLE IF NOT EXISTS production_products_cache (
    product_id BIGINT PRIMARY KEY,
    symbol TEXT NOT NULL DEFAULT '',
    kolor TEXT NOT NULL DEFAULT '',
    fetched_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_production_products_cache_expires_at
    ON production_products_cache (expires_at);

CREATE TABLE IF NOT EXISTS product_stock_current (
    product_id BIGINT NOT NULL,
    stock_id INTEGER NOT NULL,
    size_id TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_orders INTEGER NOT NULL DEFAULT 0,
    fetched_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (product_id, stock_id, size_id)
);

CREATE INDEX IF NOT EXISTS idx_product_stock_current_product_stock
    ON product_stock_current (product_id, stock_id);

CREATE TABLE IF NOT EXISTS product_stock_history (
    snapshot_date DATE NOT NULL,
    product_id BIGINT NOT NULL,
    stock_id INTEGER NOT NULL,
    size_id TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_orders INTEGER NOT NULL DEFAULT 0,
    fetched_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (snapshot_date, product_id, stock_id, size_id)
);

CREATE INDEX IF NOT EXISTS idx_product_stock_history_product_stock_date
    ON product_stock_history (product_id, stock_id, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS sync_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    products_found INTEGER NOT NULL DEFAULT 0,
    batches_processed INTEGER NOT NULL DEFAULT 0,
    rows_written_current INTEGER NOT NULL DEFAULT 0,
    rows_written_history INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL
);
