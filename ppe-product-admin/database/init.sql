-- =====================================
-- PPE Product Admin Database
-- Version 1.0
-- =====================================


-- 商品分类表
DROP TABLE IF EXISTS product_category;

CREATE TABLE product_category (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    cate_id VARCHAR(100) DEFAULT NULL,

    parent_id BIGINT DEFAULT 0,

    level INT DEFAULT 1,

    category_name VARCHAR(100) NOT NULL,

    full_name VARCHAR(500) DEFAULT NULL,


    product_count INT DEFAULT 0,


    status TINYINT DEFAULT 1,

    sort_order INT DEFAULT 0,


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,


    INDEX idx_parent_id(parent_id),

    INDEX idx_cate_id(cate_id)

) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COMMENT='PPE商品分类表';



-- =====================================
-- 商品聚合表
-- =====================================

DROP TABLE IF EXISTS product_catalog;


CREATE TABLE product_catalog (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,


    -- ERP关联
    goods_id VARCHAR(100) DEFAULT NULL,

    goods_no VARCHAR(200) DEFAULT NULL,


    -- 商品名称
    product_name VARCHAR(255) NOT NULL,


    -- 分类

    category_level_1 VARCHAR(100),

    category_level_2 VARCHAR(100),

    category_level_3 VARCHAR(100),

    cate_full_name VARCHAR(500),


    -- 品牌

    brand_name VARCHAR(100),


    -- 颜色集合

    colors JSON DEFAULT NULL,


    -- 商品状态

    status TINYINT DEFAULT 1,


    -- 是否已上传文件

    has_files TINYINT DEFAULT 0,


    source_updated_at DATETIME DEFAULT NULL,


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,


    UNIQUE KEY uk_goods_id(goods_id),


    INDEX idx_category1(category_level_1),

    INDEX idx_category2(category_level_2),

    INDEX idx_category3(category_level_3),

    INDEX idx_product_name(product_name)


) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COMMENT='PPE聚合商品表';



-- =====================================
-- 商品文件表
-- =====================================

DROP TABLE IF EXISTS product_files;


CREATE TABLE product_files (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,


    product_id BIGINT NOT NULL,


    file_type VARCHAR(50) DEFAULT 'product_image',


    file_name VARCHAR(255),


    file_url VARCHAR(1000),


    file_size BIGINT DEFAULT NULL,


    file_width INT DEFAULT NULL,

    file_height INT DEFAULT NULL,


    remark VARCHAR(500),


    status TINYINT DEFAULT 1,


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,


    INDEX idx_product_id(product_id),


    CONSTRAINT fk_product_files_product

    FOREIGN KEY(product_id)

    REFERENCES product_catalog(id)

    ON DELETE CASCADE


) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COMMENT='PPE商品文件管理表';



