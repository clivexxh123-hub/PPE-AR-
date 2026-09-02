CREATE TABLE IF NOT EXISTS ai_model_assets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    model_key VARCHAR(191) NOT NULL,
    model_name VARCHAR(120) NOT NULL,
    gender ENUM('male', 'female', 'unisex') NOT NULL,
    shot_type ENUM('full_body', 'half_body') NOT NULL DEFAULT 'full_body',
    view_type ENUM('front', 'slight_side') NOT NULL DEFAULT 'front',
    image_name VARCHAR(255) NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    remark VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_ai_model_assets_gender (gender),
    KEY idx_ai_model_assets_shot_type (shot_type),
    KEY idx_ai_model_assets_view_type (view_type),
    KEY idx_ai_model_assets_name (model_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_scene_assets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    scene_key VARCHAR(191) NOT NULL,
    scene_name VARCHAR(120) NOT NULL,
    industry VARCHAR(120) NOT NULL,
    image_name VARCHAR(255) NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    remark VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_ai_scene_assets_industry (industry),
    KEY idx_ai_scene_assets_name (scene_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_logo_assets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    logo_key VARCHAR(191) NOT NULL,
    region VARCHAR(120) NOT NULL,
    company_name VARCHAR(191) NOT NULL,
    logo_name VARCHAR(255) NULL,
    logo_url VARCHAR(500) NULL,
    remark VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_ai_logo_assets_key (logo_key),
    KEY idx_ai_logo_assets_region (region),
    KEY idx_ai_logo_assets_company (company_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
