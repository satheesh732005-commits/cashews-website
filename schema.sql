CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(160) NOT NULL,
    mobile CHAR(10) NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    address VARCHAR(500) NOT NULL DEFAULT '',
    city VARCHAR(120) NOT NULL DEFAULT '',
    pincode CHAR(6) NOT NULL DEFAULT '',
    state VARCHAR(80) NOT NULL DEFAULT '',
    role VARCHAR(20) NOT NULL DEFAULT 'customer',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_users_role CHECK (role IN ('customer', 'admin'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(40) NOT NULL,
    grade VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    ingredients VARCHAR(500) NOT NULL,
    best_for VARCHAR(500) NOT NULL,
    nutrition_json JSON NOT NULL,
    shelf_life VARCHAR(120) NOT NULL DEFAULT '6 months from packing',
    storage_instructions VARCHAR(255) NOT NULL DEFAULT 'Airtight container, cool and dry place',
    packaging VARCHAR(120) NOT NULL DEFAULT 'Vacuum-sealed pouch',
    allergen VARCHAR(120) NOT NULL DEFAULT 'Contains tree nuts',
    origin VARCHAR(160) NOT NULL DEFAULT 'Panruti, Tamil Nadu',
    image_url VARCHAR(500) NOT NULL DEFAULT '/images/cashew-bowl.png',
    rating DECIMAL(2,1) NOT NULL DEFAULT 4.8,
    review_count INT UNSIGNED NOT NULL DEFAULT 0,
    stock INT UNSIGNED NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_products_catalog (is_active, category, grade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS product_sizes (
    product_id INT UNSIGNED NOT NULL,
    size VARCHAR(12) NOT NULL,
    weight_grams SMALLINT UNSIGNED NOT NULL,
    price INT UNSIGNED NOT NULL,
    PRIMARY KEY (product_id, size),
    CONSTRAINT fk_product_sizes_product FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orders (
    order_number VARCHAR(24) NOT NULL PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    placed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payment_method VARCHAR(16) NOT NULL,
    payment_status VARCHAR(40) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'Placed',
    cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    address JSON NOT NULL,
    subtotal INT UNSIGNED NOT NULL,
    delivery INT UNSIGNED NOT NULL,
    total INT UNSIGNED NOT NULL,
    razorpay_order_id VARCHAR(64) NULL UNIQUE,
    razorpay_payment_id VARCHAR(64) NULL UNIQUE,
    refund_status VARCHAR(40) NULL,
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id),
    KEY idx_orders_user_date (user_id, placed_at),
    KEY idx_orders_status_date (status, placed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(24) NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    pack_size VARCHAR(12) NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    unit_price INT UNSIGNED NOT NULL,
    CONSTRAINT fk_items_order FOREIGN KEY (order_number) REFERENCES orders(order_number)
        ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(id),
    KEY idx_order_items_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS order_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(24) NOT NULL,
    status VARCHAR(32) NOT NULL,
    note VARCHAR(500) NOT NULL DEFAULT '',
    changed_by BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_history_order FOREIGN KEY (order_number) REFERENCES orders(order_number)
        ON DELETE CASCADE,
    CONSTRAINT fk_history_user FOREIGN KEY (changed_by) REFERENCES users(id)
        ON DELETE SET NULL,
    KEY idx_history_order_date (order_number, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
