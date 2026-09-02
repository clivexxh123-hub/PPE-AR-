SET NAMES utf8mb4;

ALTER TABLE business_generation_records
    ADD COLUMN customer_id CHAR(36) NULL AFTER tenant_id,
    ADD COLUMN customer_name_at_event VARCHAR(120) NULL AFTER customer_id,
    ADD COLUMN display_name VARCHAR(255) NULL AFTER customer_name_at_event,
    ADD COLUMN case_template_id VARCHAR(64) NULL AFTER display_name,
    ADD COLUMN case_template_name_at_event VARCHAR(160) NULL AFTER case_template_id,
    ADD COLUMN version_no INT NOT NULL DEFAULT 1 AFTER case_template_name_at_event,
    ADD COLUMN print_preflight_json JSON NULL AFTER parameters_json,
    ADD INDEX idx_generation_records_customer_time (customer_id, created_at),
    ADD INDEX idx_generation_records_display_name (display_name),
    ADD CONSTRAINT fk_generation_records_customer
        FOREIGN KEY (customer_id) REFERENCES business_customers(id);

CREATE TABLE IF NOT EXISTS business_case_templates (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    industry VARCHAR(100) NOT NULL,
    work_scene VARCHAR(120) NOT NULL,
    description VARCHAR(600) NULL,
    standard_reference VARCHAR(255) NULL,
    standard_review_status ENUM('pending_review', 'reviewed') NOT NULL DEFAULT 'pending_review',
    selection_json JSON NOT NULL,
    print_rules_json JSON NOT NULL,
    preview_url VARCHAR(500) NULL,
    status ENUM('draft', 'published', 'disabled') NOT NULL DEFAULT 'draft',
    version_no INT NOT NULL DEFAULT 1,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    UNIQUE KEY uk_case_templates_name_version (tenant_id, name, version_no),
    INDEX idx_case_templates_publish (tenant_id, status, sort_order)
);

INSERT INTO business_case_templates (
    id, tenant_id, name, industry, work_scene, description,
    standard_reference, standard_review_status,
    selection_json, print_rules_json, status, version_no, sort_order
) VALUES
(
    'construction-general-v1', 'shoudun-ppe', '建筑普通作业标准方案', '建筑', '普通作业',
    '面向建筑工地日常巡检、物料搬运和现场协同的基础 PPE 视觉方案。',
    '标准依据待甲方合规负责人复核', 'pending_review',
    '{"productKeywords":["安全帽","反光衣"],"sceneKeywords":["建筑","工地"],"modelFilters":{"shotType":"full_body","view":"front","gender":"all"}}',
    '{"logoTreatment":"preserve_brand_color","safeAreaRequired":true,"lockedAspectRatio":true}',
    'published', 1, 10
),
(
    'construction-electric-v1', 'shoudun-ppe', '建筑电工作业标准方案', '建筑', '电工作业',
    '面向临时用电、设备接线和电气巡检场景的 PPE 视觉方案。',
    '标准依据待甲方合规负责人复核', 'pending_review',
    '{"productKeywords":["安全帽","反光衣","劳保鞋"],"sceneKeywords":["电工","建筑"],"modelFilters":{"shotType":"full_body","view":"front","gender":"all"}}',
    '{"logoTreatment":"preserve_brand_color","safeAreaRequired":true,"lockedAspectRatio":true}',
    'published', 1, 20
),
(
    'construction-confined-space-v1', 'shoudun-ppe', '建筑有限空间作业方案', '建筑', '有限空间',
    '面向有限空间进入前检查和现场监护展示的 PPE 视觉方案。',
    '标准依据待甲方合规负责人复核', 'pending_review',
    '{"productKeywords":["安全帽","反光衣","手套"],"sceneKeywords":["有限空间","建筑"],"modelFilters":{"shotType":"full_body","view":"front","gender":"all"}}',
    '{"logoTreatment":"preserve_brand_color","safeAreaRequired":true,"lockedAspectRatio":true}',
    'published', 1, 30
)
ON DUPLICATE KEY UPDATE
    name=VALUES(name),
    industry=VALUES(industry),
    work_scene=VALUES(work_scene),
    description=VALUES(description),
    standard_reference=VALUES(standard_reference),
    standard_review_status=VALUES(standard_review_status),
    selection_json=VALUES(selection_json),
    print_rules_json=VALUES(print_rules_json),
    status=VALUES(status),
    version_no=VALUES(version_no),
    sort_order=VALUES(sort_order);
