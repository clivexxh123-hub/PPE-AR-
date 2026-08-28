CREATE TABLE IF NOT EXISTS business_product_showcase_profiles (
    product_id BIGINT PRIMARY KEY,
    material VARCHAR(500) NULL,
    unit_name VARCHAR(80) NULL,
    specification VARCHAR(1000) NULL,
    packaging_specification VARCHAR(1000) NULL,
    execution_standard VARCHAR(500) NULL,
    selling_points_json JSON NOT NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_showcase_profile_product FOREIGN KEY (product_id) REFERENCES product_catalog(id)
);
